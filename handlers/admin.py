"""
Handler для ручной загрузки фото и управления постами.
"""
import os
import logging
import uuid
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from config import ADMIN_ID
from database import db
from utils import router_ai, image_compressor

router = Router()

# Настройки папок
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class PhotoStates(StatesGroup):
    """Состояния для загрузки фото"""
    waiting_for_photo = State()
    waiting_for_description = State()
    waiting_for_channel = State()


class AdminStates(StatesGroup):
    """Состояния для админ-команд"""
    waiting_for_edit_text = State()
    waiting_for_new_caption = State()


def get_channel_keyboard():
    """Клавиатура выбора канала"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏠 ТЕРИОН", callback_data="channel:terion"),
                InlineKeyboardButton(text="🏡 ДОМ ГРАНД", callback_data="channel:dom_grand")
            ],
            [
                InlineKeyboardButton(text="📤 ТГ + ВК", callback_data="channel:both")
            ]
        ]
    )


def get_post_keyboard(post_id: int):
    """Клавиатура управления постом"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_post:{post_id}"),
                InlineKeyboardButton(text="✅ Опубликовать", callback_data="publish_post:{post_id}")
            ],
            [
                InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_post:{post_id}")
            ]
        ]
    )


def get_admin_keyboard():
    """Клавиатура админа"""
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📸 Загрузить фото")],
            [KeyboardButton(text="📋 Мои черновики")],
            [KeyboardButton(text="📊 Статистика")]
        ],
        resize_keyboard=True
    )


@router.message(F.text == "/admin")
async def admin_menu(message: Message):
    """Меню администратора"""
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Доступ запрещён")
        return
    
    await message.answer(
        "👨‍💼 Панель администратора\n\n"
        "📸 /upload_photo — загрузить фото объекта\n"
        "📋 /my_posts — мои черновики\n"
        "📊 /stats — статистика",
        reply_markup=get_admin_keyboard()
    )


@router.message(F.text == "📸 Загрузить фото")
async def start_upload_photo(message: Message, state: FSMContext):
    """Начало загрузки фото"""
    if message.from_user.id != ADMIN_ID:
        return
    
    await state.set_state(PhotoStates.waiting_for_photo)
    await message.answer(
        "📸 Отправьте фото объекта\n\n"
        "Можно отправить 1 фото или альбом (до 10 фото)"
    )


@router.message(PhotoStates.waiting_for_photo, F.photo)
async def process_photo(message: Message, state: FSMContext):
    """Обработка загруженного фото"""
    user_id = message.from_user.id
    
    # Создаем уникальную папку для фото
    session_id = str(uuid.uuid4())[:8]
    session_dir = os.path.join(UPLOAD_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    # Скачиваем фото
    photo_paths = []
    
    if message.photo:
        # Одно фото или альбом
        for idx, photo in enumerate(message.photo):
            file = await message.bot.get_file(photo.file_id)
            ext = ".jpg"
            path = os.path.join(session_dir, f"photo_{idx}{ext}")
            await message.bot.download_file(file.file_path, path)
            
            # Сжимаем для ТГ
            compressed = image_compressor.prepare_for_telegram(path)
            if compressed:
                photo_paths.append(compressed)
    
    elif message.document and message.document.mime_type.startswith('image/'):
        # Документ-изображение
        file = await message.bot.get_file(message.document.file_id)
        ext = image_compressor.get_file_extension(message.document.mime_type)
        path = os.path.join(session_dir, f"document{ext}")
        await message.bot.download_file(file.file_path, path)
        
        # Сжимаем
        compressed = image_compressor.prepare_for_telegram(path)
        if compressed:
            photo_paths.append(compressed)
    
    if not photo_paths:
        await message.answer("❌ Ошибка загрузки фото")
        return
    
    # Сохраняем пути в состояние
    await state.update_data(
        photo_paths=photo_paths,
        session_id=session_id
    )
    
    await message.answer(
        f"✅ Загружено {len(photo_paths)} фото\n\n"
        "Теперь напишите описание (или /skip если пропустить)"
    )
    await state.set_state(PhotoStates.waiting_for_description)


@router.message(PhotoStates.waiting_for_description)
async def process_description(message: Message, state: FSMContext):
    """Обработка описания и анализ через ИИ"""
    data = await state.get_data()
    photo_paths = data.get('photo_paths', [])
    session_id = data.get('session_id')
    user_id = message.from_user.id
    
    # Если пропуск - генерируем описание через ИИ
    if message.text and message.text.lower() == "/skip":
        description = await analyze_photos_with_ai(photo_paths)
    else:
        description = message.text
    
    # Анализируем фото через ИИ для улучшения описания
    ai_context = await analyze_photos_with_ai(photo_paths)
    
    await state.update_data(
        description=description,
        ai_context=ai_context,
        user_id=user_id,
        username=message.from_user.username or ""
    )
    
    # Спрашиваем канал
    await message.answer(
        f"📝 Описание сохранено!\n\n"
        f"🤖 ИИ-анализ фото:\n{ai_context}\n\n"
        "Выберите канал для публикации:",
        reply_markup=get_channel_keyboard()
    )
    await state.set_state(PhotoStates.waiting_for_channel)


async def analyze_photos_with_ai(photo_paths: list) -> str:
    """Анализирует фото через ИИ (упрощенная версия)"""
    # В реальной версии здесь был бы анализ изображений
    # Пока возвращаем заглушку
    return "📸 Фото объекта готовы к публикации"


@router.callback_query(PhotoStates.waiting_for_channel)
async def process_channel(callback: CallbackQuery, state: FSMContext):
    """Выбор канала и сохранение поста"""
    data = await state.get_data()
    
    channel = callback.data.replace("channel:", "")
    channel_map = {
        'terion': ('ТЕРИОН', 'terion'),
        'dom_grand': ('ДОМ ГРАНД', 'dom_grand'),
        'both': ('ТГ + ВК', 'both')
    }
    
    channel_name, channel_key = channel_map.get(channel, ('ТЕРИОН', 'terion'))
    
    # Сохраняем пост в БД
    post_id = await db.save_post(
        post_type='photo',
        title=data.get('description', '')[:100],
        body=data.get('description', ''),
        cta="📩 Записаться на консультацию: @Parkhovenko_i_kompaniya_bot",
        publish_date=datetime.now(),
        channel=channel_key,
        theme="Фото объекта",
        image_url=data.get('photo_paths', [None])[0],
        admin_id=data.get('user_id'),
        status='draft'
    )
    
    # Формируем сообщение для рабочей группы
    text = (
        f"📸 <b>Новый фото-пост</b>\n\n"
        f"📝 Описание: {data.get('description', 'Без описания')}\n\n"
        f"🤖 ИИ-анализ: {data.get('ai_context', '')}\n\n"
        f"📍 Канал: {channel_name}\n"
        f"👤 Админ: @{data.get('username', 'неизвестно')}"
    )
    
    # Отправляем в группу
    from config import LEADS_GROUP_CHAT_ID
    from dotenv import getenv
    
    thread_id = int(getenv("THREAD_ID_DRAFTS", "85"))
    
    # Отправляем с фото
    if data.get('photo_paths'):
        try:
            if len(data['photo_paths']) == 1:
                await callback.bot.send_photo(
                    chat_id=LEADS_GROUP_CHAT_ID,
                    photo=FSInputFile(data['photo_paths'][0]),
                    caption=text,
                    reply_markup=get_post_keyboard(post_id),
                    message_thread_id=thread_id
                )
            else:
                # Альбом
                media = [InputMediaPhoto(media=FSInputFile(p)) for p in data['photo_paths']]
                media[0].caption = text
                await callback.bot.send_media_group(
                    chat_id=LEADS_GROUP_CHAT_ID,
                    media=media,
                    message_thread_id=thread_id
                )
                # Отправляем кнопки отдельно
                await callback.bot.send_message(
                    chat_id=LEADS_GROUP_CHAT_ID,
                    text="Управление постом:",
                    reply_markup=get_post_keyboard(post_id),
                    message_thread_id=thread_id
                )
        except Exception as e:
            logging.error(f"Ошибка отправки фото в группу: {e}")
            await callback.bot.send_message(
                chat_id=LEADS_GROUP_CHAT_ID,
                text=text,
                reply_markup=get_post_keyboard(post_id),
                message_thread_id=thread_id
            )
    
    await callback.message.edit_text(
        f"✅ Пост сохранён! ID: {post_id}\n"
        f"📍 Канал: {channel_name}\n\n"
        "📤 Отправлен в рабочую группу на утверждение."
    )
    await callback.answer()
    
    await state.clear()


@router.message(F.text == "📋 Мои черновики")
async def my_posts(message: Message):
    """Показать черновики админа"""
    if message.from_user.id != ADMIN_ID:
        return
    
    posts = await db.get_draft_posts()
    
    if not posts:
        await message.answer("📭 У вас нет черновиков")
        return
    
    response = "📋 <b>Ваши черновики:</b>\n\n"
    for post in posts[:10]:  # Показываем последние 10
        date = post.get('publish_date', '')[:10]
        response += f"• ID {post['id']}: {post.get('type', 'photo')} — {date}\n"
    
    await message.answer(response)


@router.callback_query(F.data.startswith("edit_post:"))
async def edit_post(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования поста"""
    post_id = int(callback.data.replace("edit_post:", ""))
    
    # Получаем пост
    posts = await db.get_draft_posts()
    post = next((p for p in posts if p['id'] == post_id), None)
    
    if not post:
        await callback.message.edit_text("❌ Пост не найден")
        await callback.answer()
        return
    
    await state.update_data(edit_post_id=post_id)
    
    await callback.message.edit_text(
        f"✏️ <b>Редактирование поста #{post_id}</b>\n\n"
        f"<b>Текущий текст:</b>\n{post.get('body', 'Пусто')}\n\n"
        "Напишите новый текст:"
    )
    
    await state.set_state(AdminStates.waiting_for_new_caption)
    await callback.answer()


@router.message(AdminStates.waiting_for_new_caption)
async def save_edited_caption(message: Message, state: FSMContext):
    """Сохранение отредактированного текста"""
    data = await state.get_data()
    post_id = data.get('edit_post_id')
    
    if message.text:
        # Обновляем пост
        await db.update_content_plan_entry(
            post_id=post_id,
            body=message.text
        )
        
        await message.answer(f"✅ Текст поста #{post_id} обновлён!")
    
    await state.clear()


@router.callback_query(F.data.startswith("delete_post:"))
async def delete_post(callback: CallbackQuery):
    """Удаление поста"""
    post_id = int(callback.data.replace("delete_post:", ""))
    
    await db.delete_post(post_id)
    
    await callback.message.edit_text(
        f"❌ Пост #{post_id} удалён"
    )
    await callback.answer()


@router.message(F.text == "📊 Статистика")
async def stats(message: Message):
    """Статистика постов"""
    if message.from_user.id != ADMIN_ID:
        return
    
    posts = await db.get_draft_posts()
    published = [p for p in posts if p.get('status') == 'published']
    
    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"📝 Черновиков: {len(posts)}\n"
        f"✅ Опубликовано: {len(published)}"
    )


# Обработка команды /upload_photo
@router.message(F.text == "/upload_photo")
async def cmd_upload_photo(message: Message, state: FSMContext):
    """Команда загрузки фото"""
    await start_upload_photo(message, state)


# Обработка команды /my_posts
@router.message(F.text == "/my_posts")
async def cmd_my_posts(message: Message):
    """Команда показа черновиков"""
    await my_posts(message)


# Обработка команды /stats
@router.message(F.text == "/stats")
async def cmd_stats(message: Message):
    """Команда статистики"""
    await stats(message)
