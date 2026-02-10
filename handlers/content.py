"""
Content Handler — создание и публикация контента (aiogram 3.x).
Интегрирован с ViralHooksAgent, ContentRepurposeAgent, VKService.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime
import logging

from database import db
from agents.viral_hooks_agent import viral_hooks_agent
from agents.content_repurpose_agent import content_repurpose_agent
from services.vk_service import vk_service
from config import (
    CHANNEL_ID, DOM_GRAND_CHANNEL_ID, 
    THREAD_ID_DRAFTS, LEADS_GROUP_CHAT_ID
)

logger = logging.getLogger(__name__)
content_router = Router()


# === FSM STATES ===
class ContentStates(StatesGroup):
    main_menu = State()
    ai_photo = State()          # Фото + ИИ-пост
    ai_text = State()           # Только текст
    ai_series = State()         # Серия постов
    select_variant = State()     # Выбор варианта
    publish = State()           # Публикация


# === KEYBOARDS ===
def get_content_menu():
    """Главное меню контента"""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📸 Фото + ИИ-пост", callback_data="ai_photo"))
    markup.add(InlineKeyboardButton("📝 Только текст → ИИ", callback_data="ai_text"))
    markup.add(InlineKeyboardButton("📅 Серия постов", callback_data="ai_series"))
    markup.add(InlineKeyboardButton("📋 Мои посты", callback_data="my_posts"))
    return markup


def get_back_btn():
    """Кнопка назад"""
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton("◀️ В меню", callback_data="content_back")
    )


def get_publish_btns(post_id: int):
    """Кнопки публикации"""
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("📤 TERION", callback_data=f"publish_terion_{post_id}"),
        InlineKeyboardButton("📤 ДОМ ГРАНД", callback_data=f"publish_dom_{post_id}")
    )
    markup.add(
        InlineKeyboardButton("📤 ВК", callback_data=f"publish_vk_{post_id}")
    )
    markup.add(InlineKeyboardButton("◀️ В меню", callback_data="content_back"))
    return markup


# === MAIN MENU ===
@content_router.callback_query(F.data == "mode:content")
async def content_menu(callback: CallbackQuery, state: FSMContext):
    """Меню контента"""
    await callback.message.edit_text(
        "🎯 <b>Content Bot</b>\n\n"
        "🤖 <b>AI-агенты делают рутину за вас!</b>\n\n"
        "📸 <b>Фото + ИИ-пост</b> — загрузите фото, ИИ создаст пост\n"
        "📝 <b>Только текст → ИИ</b> — тема, ИИ улучшит\n"
        "📅 <b>Серия постов</b> — тема + дней, ИИ сделает цепочку\n"
        "📋 <b>Мои посты</b> — просмотр и публикация\n\n"
        "Выберите:",
        reply_markup=get_content_menu(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.main_menu)
    await callback.answer()


# === CALLBACKS ===
@content_router.callback_query(F.data.startswith("content_"))
async def content_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопок меню"""
    user_id = callback.from_user.id
    data = callback.data
    
    if data == "content_back":
        await content_menu(callback, state)
        return
    
    if data == "ai_photo":
        user_state = {"step": "ai_photo_wait_photo"}
        await state.update_data(user_state=user_state)
        await callback.message.edit_text(
            "📸 <b>Фото + ИИ-пост</b>\n\n"
            "Загрузите фото объекта (можно несколько):",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
        await state.set_state(ContentStates.ai_photo)
        
    elif data == "ai_text":
        user_state = {"step": "ai_text_wait_topic"}
        await state.update_data(user_state=user_state)
        await callback.message.edit_text(
            "📝 <b>Только текст → ИИ</b>\n\n"
            "Введите тему поста:",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
        await state.set_state(ContentStates.ai_text)
        
    elif data == "ai_series":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("7 дней", callback_data="series_7"))
        markup.add(InlineKeyboardButton("14 дней", callback_data="series_14"))
        markup.add(InlineKeyboardButton("30 дней", callback_data="series_30"))
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="content_back"))
        await callback.message.edit_text(
            "📅 <b>Серия постов</b>\n\nВыберите длительность:",
            reply_markup=markup,
            parse_mode="HTML"
        )
        await state.set_state(ContentStates.ai_series)
        
    elif data == "my_posts":
        await show_my_posts(callback, state)
        
    elif data.startswith("series_"):
        days = int(data.split("_")[1])
        user_state = {"step": "series_wait_topic", "days": days}
        await state.update_data(user_state=user_state)
        await callback.message.edit_text(
            f"📅 <b>Серия на {days} дней</b>\n\n"
            "Введите тему:",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
        await state.set_state(ContentStates.ai_series)
        
    elif data.startswith("publish_"):
        await handle_publish(callback, state)
    
    await callback.answer()


# === AI PHOTO ===
@content_router.message(ContentStates.ai_photo, F.photo)
async def ai_photo_handler(message: Message, state: FSMContext):
    """Получаем фото"""
    data = await state.get_data()
    user_state = data.get("user_state", {})
    photos = user_state.get("photos", [])
    
    file_id = message.photo[-1].file_id
    photos.append(file_id)
    user_state["photos"] = photos
    await state.update_data(user_state=user_state)
    
    count = len(photos)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Хватит фото", callback_data="ai_photo_done"))
    markup.add(InlineKeyboardButton("◀️ В меню", callback_data="content_back"))
    
    await message.answer(
        f"✅ Фото {count}!\n\n"
        "Теперь введите тему поста:",
        reply_markup=markup
    )


@content_router.callback_query(ContentStates.ai_photo, F.data == "ai_photo_done")
async def ai_photo_done(callback: CallbackQuery, state: FSMContext):
    """Фото готовы — ждём тему"""
    await callback.message.edit_text(
        "🎨 ИИ создаёт варианты постов...",
        reply_markup=get_back_btn()
    )
    
    data = await state.get_data()
    topic = data.get("topic", "перепланировка")
    photos = data.get("user_state", {}).get("photos", [])
    
    # Генерируем варианты через ViralHooksAgent
    hooks = await viral_hooks_agent.generate_hooks(topic, count=5)
    
    variants = []
    for hook in hooks:
        text = f"{hook['text']}\n\n"
        text += f"Подробный экспертный разбор темы «{topic}».\n\n"
        text += "💡 Обращайтесь к профи — @Parkhovenko_i_kompaniya_bot"
        
        variants.append({
            "type": hook.get("category", "экспертный"),
            "text": text,
            "topic": topic,
            "photos": photos
        })
    
    # Сохраняем варианты
    user_state = data.get("user_state", {})
    user_state["variants"] = variants
    await state.update_data(user_state=user_state)
    
    # Показываем варианты
    for i, v in enumerate(variants, 1):
        preview = v["text"][:200] + "..."
        await callback.message.answer(
            f"📝 <b>Вариант {i}: {v['type']}</b>\n\n{preview}",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton(f"✅ Выбрать {i}", callback_data=f"select_variant_{i}")
            ),
            parse_mode="HTML"
        )
    
    await callback.message.answer(
        "Выберите вариант или введите тему для регенерации:",
        reply_markup=get_back_btn()
    )
    await state.set_state(ContentStates.select_variant)


# === AI TEXT ===
@content_router.message(ContentStates.ai_text)
async def ai_text_handler(message: Message, state: FSMContext):
    """Получаем тему → генерируем пост"""
    topic = message.text
    await state.update_data(topic=topic)
    
    # Генерируем через ViralHooksAgent
    hooks = await viral_hooks_agent.generate_hooks(topic, count=1)
    hook = hooks[0] if hooks else {"text": f"📢 {topic}"}
    
    text = f"<b>{hook['text']}</b>\n\n"
    text += f"Разберём по полочкам: что нужно знать о {topic.lower()}.\n\n"
    text += "🔑 Ключевые моменты:\n"
    text += "• Пункт 1\n• Пункт 2\n• Пункт 3\n\n"
    text += "💡 Вывод: это профессиональная задача.\n\n"
    text += "👉 Запишитесь: @Parkhovenko_i_kompaniya_bot"
    
    # Сохраняем пост
    post_id = await db.add_content_post(
        title=topic,
        body=text,
        cta="Записаться: @Parkhovenko_i_kompaniya_bot",
        channel="draft"
    )
    
    await message.answer(
        f"📝 <b>ИИ-пост готов!</b>\n\n{text}",
        reply_markup=get_publish_btns(post_id),
        parse_mode="HTML"
    )


# === AI SERIES ===
@content_router.message(ContentStates.ai_series)
async def ai_series_handler(message: Message, state: FSMContext):
    """Серия постов"""
    topic = message.text
    data = await state.get_data()
    days = data.get("user_state", {}).get("days", 7)
    
    chain = generate_series_chain(topic, days)
    
    post_ids = []
    for item in chain:
        post_id = await db.add_content_post(
            title=item["topic"],
            body=item["text"],
            cta="@Parkhovenko_i_kompaniya_bot",
            channel="draft",
            scheduled_date=item.get("date")
        )
        post_ids.append(post_id)
    
    text = f"📅 <b>Серия на {days} дней готова!</b>\n\n"
    for item in chain[:5]:
        text += f"📌 День {item['day']}: {item['topic']}\n"
    
    await message.answer(text, reply_markup=get_back_btn(), parse_mode="HTML")


def generate_series_chain(topic: str, days: int):
    """Генерирует цепочку постов"""
    chain = []
    themes = [
        ("Боль", f"😱 Опасность: штрафы за {topic.lower()}"),
        ("Эксперт", f"📋 Что можно и нельзя при {topic.lower()}"),
        ("Эксперт", f"📁 Какие документы нужны для {topic.lower()}"),
        ("Эксперт", f"🔄 Как проходит {topic.lower()}"),
        ("Соцдок", f"🏠 Наши кейсы: успешные проекты"),
        ("Соцдок", f"⭐ Отзывы клиентов"),
        ("CTA", f"🎯 Запишитесь на консультацию"),
    ]
    
    for i, (theme, text_template) in enumerate(themes[:days], 1):
        hook_text = text_template.format(topic=topic)
        text = f"<b>{hook_text}</b>\n\n"
        text += "Подробный экспертный разбор темы.\n\n"
        text += "💡 Подробности у специалистов: @Parkhovenko_i_kompaniya_bot"
        
        chain.append({
            "day": i,
            "theme": theme,
            "topic": hook_text,
            "text": text
        })
    
    return chain


# === MY POSTS ===
async def show_my_posts(callback: CallbackQuery, state: FSMContext):
    """Показывает посты пользователя"""
    posts = await db.get_content_posts(limit=20)
    
    if not posts:
        await callback.message.edit_text(
            "📭 Постов пока нет.",
            reply_markup=get_back_btn()
        )
        return
    
    text = "📋 <b>Мои посты</b>\n\n"
    for post in posts[-10:]:
        status = "⏳" if post.get("status") == "draft" else "📤"
        topic = post.get("title", post.get("body", "Пост")[:25])
        text += f"{status} #{post.get('id', '?')} - {topic}\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )


# === PUBLISH ===
async def handle_publish(callback: CallbackQuery, state: FSMContext):
    """Публикация поста"""
    data = callback.data
    # publish_terion_123 -> parts = ['publish', 'terion', '123']
    parts = data.split("_")
    if len(parts) < 3:
        await callback.answer("Ошибка формата!")
        return
    channel = parts[1]
    post_id = int(parts[2])
    
    post = await db.get_content_post(post_id)
    if not post:
        await callback.answer("Пост не найден!")
        return
    
    # Определяем канал
    channel_id = CHANNEL_ID if channel == "terion" else DOM_GRAND_CHANNEL_ID
    
    # Публикуем
    success = False
    try:
        if post.get("image_url"):
            await callback.bot.send_photo(
                chat_id=channel_id,
                photo=post["image_url"],
                caption=post["body"],
                parse_mode="HTML"
            )
        else:
            await callback.bot.send_message(
                chat_id=channel_id,
                text=post["body"],
                parse_mode="HTML"
            )
        success = True
        
        # В ВК
        if channel == "vk" and vk_service.vk_token:
            vk_text = f"{post['title']}\n\n{post['body']}"
            if post.get("image_url"):
                await vk_service.post_with_photos(vk_text, [post["image_url"]])
            else:
                await vk_service.post(vk_text)
        
        await db.update_content_post(post_id, status="published")
        
        await callback.answer("✅ Опубликовано!")
        
    except Exception as e:
        logger.error(f"Publish error: {e}")
        await callback.answer(f"❌ Ошибка: {e}")


# === ECHO ===
@content_router.message()
async def content_echo(message: Message, state: FSMContext):
    """Эхо для отладки"""
    current_state = await state.get_state()
    await message.answer(f"DEBUG: state={current_state}")
