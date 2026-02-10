"""
Content Handler — TERION Ecosystem (v2.0)
Публикация контента: TG + VK + Max + Geo Spy
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, ContentTypesFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from PIL import Image
import logging
import io

from database import db
from agents.viral_hooks_agent import viral_hooks_agent
from content_agent import ContentAgent
from config import (
    CHANNEL_ID_TERION, 
    CHANNEL_ID_DOM_GRAD, 
    VK_GROUP_ID, 
    LEADS_GROUP_CHAT_ID, 
    THREAD_ID_NEWS, 
    THREAD_ID_CONTENT_PLAN,
    THREAD_ID_DRAFTS,
    THREAD_ID_LOGS,
    THREAD_ID_HOT_LEADS,
    VK_QUIZ_LINK
)
from services.vk_service import vk_service

content_agent = ContentAgent()
logger = logging.getLogger(__name__)

content_router = Router()


# === FSM STATES ===
class ContentStates(StatesGroup):
    main_menu = State()
    ai_photo = State()
    ai_text = State()
    ai_series = State()
    select_variant = State()
    publish = State()
    edit_post = State()


# === KEYBOARDS ===
def get_main_reply_menu() -> ReplyKeyboardMarkup:
    """Reply-меню TERION"""
    kb = [
        [KeyboardButton(text="📸 Фото + пост"), KeyboardButton(text="📅 7 дней прогрева")],
        [KeyboardButton(text="🎨 ИИ-Визуал"), KeyboardButton(text="📋 Интерактивный План")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_content_menu() -> InlineKeyboardMarkup:
    """Главное меню TERION (inline)"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Создать пост", callback_data="menu:create")
    builder.button(text="🗓 Контент-план", callback_data="menu:plan")
    builder.button(text="📸 Фото + ИИ-текст", callback_data="menu:photo")
    builder.button(text="📰 Новости", callback_data="menu:news")
    return builder.as_markup()


def get_back_btn() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ В меню", callback_data="content_back")
    return builder.as_markup()


def get_draft_btns(post_id: int) -> InlineKeyboardMarkup:
    """Кнопки для постов в топике 85 (Черновики)"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 ВЕЗДЕ", callback_data=f"publish_all:{post_id}")
    builder.button(text="✏️ Редактировать", callback_data=f"edit:{post_id}")
    builder.button(text="🗑 Удалить", callback_data=f"delete:{post_id}")
    builder.adjust(3)
    return builder.as_markup()


def get_publish_btns(post_id: int) -> InlineKeyboardMarkup:
    """Кнопки публикации"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 ВЕЗДЕ", callback_data=f"publish_all:{post_id}")
    builder.button(text="🎨 ИИ-фото", callback_data=f"gen_image:{post_id}")
    builder.button(text="◀️ В меню", callback_data="content_back")
    builder.adjust(2, 1)
    return builder.as_markup()


# === /START ===
@content_router.message(CommandStart())
async def content_start(message: Message, state: FSMContext):
    """Старт Content Bot TERION - Reply-меню"""
    await state.clear()
    await message.answer(
        "🎯 <b>TERION Content Bot</b>\n\nВыберите действие в меню ниже:", 
        reply_markup=get_main_reply_menu(), 
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.main_menu)


# === REPLY MENU HANDLERS ===
@content_router.message(F.text == "📸 Фото + пост")
async def reply_menu_photo(callback: Message, state: FSMContext):
    """Reply-кнопка: Фото + пост"""
    await state.update_data(user_state={"step": "photo_wait"})
    await callback.answer(
        "📸 <b>Фото + пост</b>\n\n"
        "1️⃣ Загрузите фото объекта\n"
        "2️⃣ Напишите текст поста\n"
        "3️⃣ Пост отправится в рабочую группу\n\n"
        f"<b>Загрузите фото:</b>",
        reply_markup=get_main_reply_menu(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.ai_photo)


@content_router.message(F.text == "📅 7 дней прогрева")
async def reply_menu_series(callback: Message, state: FSMContext):
    """Reply-кнопка: 7 дней прогрева"""
    await state.update_data(user_state={"step": "series_wait", "days": 7})
    await callback.answer(
        "📅 <b>7 дней прогрева</b>\n\n"
        "Создаём цепочку постов для прогрева аудитории.\n\n"
        "Введите тему или продукт:",
        reply_markup=get_main_reply_menu(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.ai_series)


@content_router.message(F.text == "🎨 ИИ-Визуал")
async def reply_menu_visual(callback: Message, state: FSMContext):
    """Reply-кнопка: ИИ-Визуал"""
    await callback.answer(
        "🎨 <b>ИИ-Визуал</b>\n\n"
        "Введите описание изображения для генерации:\n\n"
        "Например: современная квартира, скандинавский стиль",
        reply_markup=get_main_reply_menu(),
        parse_mode="HTML"
    )


@content_router.message(F.text == "📋 Интерактивный План")
async def reply_menu_plan(callback: Message, state: FSMContext):
    """Reply-кнопка: Интерактивный План"""
    await callback.answer(
        "📋 <b>Интерактивный План</b>\n\n"
        "Выберите длительность контент-плана:",
        reply_markup=get_main_reply_menu(),
        parse_mode="HTML"
    )


# === NAVIGATION ===
@content_router.callback_query(F.data == "content_back")
async def content_back(callback: CallbackQuery, state: FSMContext):
    """Назад в главное меню"""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("🎯 <b>TERION Content Bot</b>\n\nВыберите:", reply_markup=get_content_menu(), parse_mode="HTML")
    await state.set_state(ContentStates.main_menu)


# === MENU: CREATE ===
@content_router.callback_query(F.data == "menu:create")
async def menu_create(callback: CallbackQuery, state: FSMContext):
    """Меню: Создать пост"""
    await callback.answer()
    builder = InlineKeyboardBuilder()
    builder.button(text="📸 Фото + Текст", callback_data="menu:photo")
    builder.button(text="📝 Только текст", callback_data="menu:text")
    builder.button(text="📅 Серия постов", callback_data="menu:series")
    builder.adjust(1)
    await callback.message.edit_text("📝 <b>Создание поста TERION</b>\n\nВыберите формат:", reply_markup=builder.as_markup(), parse_mode="HTML")


# === MENU: PHOTO (Vision + Post) ===
@content_router.callback_query(F.data == "menu:photo")
async def menu_photo(callback: CallbackQuery, state: FSMContext):
    """Меню: Фото + ИИ-текст"""
    await callback.answer()
    await state.update_data(user_state={"step": "photo_wait"})
    await callback.message.edit_text(
        "📸 <b>Фото + Текст</b>\n\n"
        "Загрузите фото объекта — ИИ проанализирует и создаст пост.\n\n"
        f"👉 Квиз: {VK_QUIZ_LINK}",
        reply_markup=get_back_btn(), 
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.ai_photo)


# === AI PHOTO HANDLER ===
@content_router.message(ContentStates.ai_photo, F.photo)
async def ai_photo_handler(message: Message, state: FSMContext):
    """Обработка фото — Vision + Генерация поста"""
    await state.update_data({"photo_id": message.photo[-1].file_id})
    
    # TODO: Vision analysis здесь
    await message.answer(
        "🔍 <b>Анализируем фото...</b>\n\n"
        "Распознаём объект и создаём экспертное описание.",
        parse_mode="HTML"
    )
    
    # Генерируем пост
    hooks = await viral_hooks_agent.generate_hooks("перепланировка", count=1)
    hook = hooks[0] if hooks else {"text": "Экспертный пост о перепланировке"}
    
    cta = f"\n\n👉 {VK_QUIZ_LINK}"
    text = f"<b>{hook['text']}</b>\n\n💡 @terion_bot{cta}"
    
    post_id = await db.add_content_post(
        title="Пост с фото", 
        body=text, 
        cta=VK_QUIZ_LINK, 
        channel="draft"
    )
    
    await state.update_data({"post_id": post_id})
    
    await message.answer_photo(
        photo=message.photo[-1].file_id,
        caption=f"✨ <b>Пост готов!</b>\n\n{text}",
        reply_markup=get_draft_btns(post_id),
        parse_mode="HTML"
    )


# === MENU: TEXT ===
@content_router.callback_query(F.data == "menu:text")
async def menu_text(callback: CallbackQuery, state: FSMContext):
    """Меню: Только текст"""
    await callback.answer()
    await state.update_data(user_state={"step": "text_wait"})
    await callback.message.edit_text(
        "📝 <b>Создание поста</b>\n\n"
        "Введите тему или идею поста:",
        reply_markup=get_back_btn(), 
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.ai_text)


# === AI TEXT HANDLER ===
@content_router.message(ContentStates.ai_text)
async def ai_text_handler(message: Message, state: FSMContext):
    """Генерация поста из текста"""
    topic = message.text
    
    hooks = await viral_hooks_agent.generate_hooks(topic, count=1)
    hook = hooks[0] if hooks else {"text": f"📢 {topic}"}
    
    cta = f"\n\n👉 {VK_QUIZ_LINK}"
    text = f"<b>{hook['text']}</b>\n\n💡 @terion_bot{cta}"
    
    post_id = await db.add_content_post(title=topic, body=text, cta=VK_QUIZ_LINK, channel="draft")
    await state.update_data({"post_id": post_id})
    
    await message.answer(
        f"✨ <b>Пост готов!</b>\n\n{text}",
        reply_markup=get_draft_btns(post_id),
        parse_mode="HTML"
    )


# === MENU: SERIES ===
@content_router.callback_query(F.data == "menu:series")
async def menu_series(callback: CallbackQuery, state: FSMContext):
    """Меню: Серия постов"""
    await callback.answer()
    builder = InlineKeyboardBuilder()
    builder.button(text="7 дней", callback_data="series_7")
    builder.button(text="14 дней", callback_data="series_14")
    builder.button(text="30 дней", callback_data="series_30")
    builder.adjust(3)
    await callback.message.edit_text("📅 <b>Серия постов</b>\n\nВыберите длительность:", reply_markup=builder.as_markup(), parse_mode="HTML")


# === PUBLISH ALL (EVERYWHERE) ===
@content_router.callback_query(F.data.startswith("publish_all:"))
async def publish_all_handler(callback: CallbackQuery, state: FSMContext):
    """Публикация ВЕЗДЕ: TG + VK + Max"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    if not post:
        await callback.answer("❌ Пост не найден")
        return
    
    await callback.message.edit_text("🚀 <b>Публикую ВЕЗДЕ!</b>", parse_mode="HTML")
    
    results = []
    
    # 1. TERION TG
    try:
        if post.get("image_url"):
            await callback.bot.send_photo(chat_id=CHANNEL_ID_TERION, photo=post["image_url"], caption=post["body"], parse_mode="HTML")
        else:
            await callback.bot.send_message(chat_id=CHANNEL_ID_TERION, text=post["body"], parse_mode="HTML")
        results.append("✅ TERION")
    except Exception as e:
        logger.error(f"TERION error: {e}")
        results.append("❌ TERION")
    
    # 2. DOM GRAD TG
    try:
        if post.get("image_url"):
            await callback.bot.send_photo(chat_id=CHANNEL_ID_DOM_GRAD, photo=post["image_url"], caption=post["body"], parse_mode="HTML")
        else:
            await callback.bot.send_message(chat_id=CHANNEL_ID_DOM_GRAD, text=post["body"], parse_mode="HTML")
        results.append("✅ ДОМ ГРАНД")
    except Exception as e:
        logger.error(f"DOM_GRAD error: {e}")
        results.append("❌ ДОМ ГРАНД")
    
    # 3. VK
    try:
        vk_result = await vk_service.post_with_quiz_cta(post["body"])
        if vk_result:
            results.append(f"✅ ВК (#{vk_result})")
        else:
            results.append("❌ ВК")
    except Exception as e:
        logger.error(f"VK error: {e}")
        results.append("❌ ВК")
    
    # 4. Max.ru
    try:
        max_result = await content_agent.post_to_max(post_id)
        if max_result:
            results.append("✅ Max.ru")
        else:
            results.append("❌ Max.ru")
    except Exception as e:
        logger.error(f"Max error: {e}")
        results.append("❌ Max.ru")
    
    await db.update_content_post(post_id, status="published")
    
    result_text = "🚀 <b>Публикация завершена!</b>\n\n" + "\n".join(results)
    await callback.message.edit_text(result_text, reply_markup=get_content_menu(), parse_mode="HTML")


# === DELETE POST ===
@content_router.callback_query(F.data.startswith("delete:"))
async def delete_handler(callback: CallbackQuery, state: FSMContext):
    """Удаление поста"""
    post_id = int(callback.data.split(":")[1])
    await db.update_content_post(post_id, status="deleted")
    await callback.message.edit_text("🗑 <b>Пост удалён</b>", reply_markup=get_content_menu(), parse_mode="HTML")


# === EDIT POST ===
@content_router.callback_query(F.data.startswith("edit:"))
async def edit_handler(callback: CallbackQuery, state: FSMContext):
    """Редактирование поста"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    if not post:
        await callback.answer("❌ Пост не найден")
        return
    
    await state.update_data({"edit_post_id": post_id})
    await callback.message.edit_text(
        f"✏️ <b>Редактирование поста</b>\n\n"
        f"<b>{post['title']}</b>\n\n"
        f"{post['body']}\n\n"
        f"Введите новый текст:",
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.edit_post)


@content_router.message(ContentStates.edit_post)
async def edit_post_handler(message: Message, state: FSMContext):
    """Сохранение отредактированного поста"""
    data = await state.get_data()
    post_id = data.get("edit_post_id")
    
    if post_id:
        await db.update_content_post(post_id, body=message.text)
        await message.answer("✅ <b>Пост обновлён!</b>", reply_markup=get_content_menu(), parse_mode="HTML")
    
    await state.clear()


# === ScoutAgent Dummy ===
try:
    from agents.scout_agent import scout_agent
except ImportError:
    class DummyScout:
        async def scout_topics(self, count=3):
            return [{"title": f"Тема {i}", "insight": "Актуальная информация"} for i in range(1, count+1)]
    scout_agent = DummyScout()
