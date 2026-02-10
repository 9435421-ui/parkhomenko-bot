"""
Content Handler — создание и публикация контента (aiogram 3.x).
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging

from database import db
from agents.viral_hooks_agent import viral_hooks_agent
from config import CHANNEL_ID, DOM_GRAND_CHANNEL_ID

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


# === KEYBOARDS (InlineKeyboardBuilder) ===
def get_content_menu() -> InlineKeyboardMarkup:
    """Главное меню контента"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Создать пост", callback_data="create_post")
    builder.button(text="📊 Статистика", callback_data="stats")
    builder.button(text="⚙️ Настройки", callback_data="settings")
    builder.adjust(1)
    return builder.as_markup()


def get_back_btn() -> InlineKeyboardMarkup:
    """Кнопка назад"""
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ В меню", callback_data="content_back")
    return builder.as_markup()


def get_publish_btns(post_id: int) -> InlineKeyboardMarkup:
    """Кнопки публикации"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📤 TERION", callback_data=f"publish_terion_{post_id}")
    builder.button(text="📤 ДОМ ГРАНД", callback_data=f"publish_dom_{post_id}")
    builder.button(text="📤 ВК", callback_data=f"publish_vk_{post_id}")
    builder.button(text="◀️ В меню", callback_data="content_back")
    return builder.as_markup()


def get_photo_done_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после загрузки фото"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Хватит фото", callback_data="ai_photo_done")
    builder.button(text="◀️ В меню", callback_data="content_back")
    return builder.as_markup()


# === /START для Content Bot ===
(message: Message, state: FSMContext):
    """Старт Content Bot — сразу показываем меню"""
    await state.clear()
    await message.answer(
        "🎯 <b>Content Bot</b>\n\nВыберите:",
        reply_markup=get_content_menu(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.main_menu)


# === MAIN MENU ===
@content_router.callback_query(F.data == "mode:content")
async def content_menu(callback: CallbackQuery, state: FSMContext):
    """Меню контента"""
    await callback.message.edit_text(
        "🎯 <b>Content Bot</b>\n\nВыберите:",
        reply_markup=get_content_menu(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.main_menu)
    await callback.answer()


# === CALLBACKS ===
@content_router.callback_query(F.data.startswith("content_"))
async def content_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопок"""
    data = callback.data
    
    if data == "content_back":
        await content_menu(callback, state)
        return
    
    if data == "create_post":
        builder = InlineKeyboardBuilder()
        builder.button(text="📸 Фото + ИИ-пост", callback_data="ai_photo")
        builder.button(text="📝 Только текст", callback_data="ai_text")
        builder.button(text="📅 Серия постов", callback_data="ai_series")
        builder.adjust(1)
        
        await callback.message.edit_text(
            "📝 <b>Создание поста</b>\n\nВыберите формат:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return
    
    if data == "ai_photo":
        await state.update_data(user_state={"step": "ai_photo_wait_photo"})
        await callback.message.edit_text(
            "📸 <b>Фото + ИИ-пост</b>\n\nЗагрузите фото объекта:",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
        await state.set_state(ContentStates.ai_photo)
        return
        
    if data == "ai_text":
        await state.update_data(user_state={"step": "ai_text_wait_topic"})
        await callback.message.edit_text(
            "📝 <b>Только текст</b>\n\nВведите тему поста:",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
        await state.set_state(ContentStates.ai_text)
        return
        
    if data == "ai_series":
        builder = InlineKeyboardBuilder()
        builder.button(text="7 дней", callback_data="series_7")
        builder.button(text="14 дней", callback_data="series_14")
        builder.button(text="30 дней", callback_data="series_30")
        builder.adjust(3)
        
        await callback.message.edit_text(
            "📅 <b>Серия постов</b>\n\nВыберите длительность:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        await state.set_state(ContentStates.ai_series)
        return
        
    if data == "stats":
        await callback.message.edit_text(
            "📊 <b>Статистика</b>\n\nВ разработке...",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
        return
        
    if data == "settings":
        await callback.message.edit_text(
            "⚙️ <b>Настройки</b>\n\nВ разработке...",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
        return
        
    if data.startswith("series_"):
        days = int(data.split("_")[1])
        user_state = {"step": "series_wait_topic", "days": days}
        await state.update_data(user_state=user_state)
        await callback.message.edit_text(
            f"📅 <b>Серия на {days} дней</b>\n\nВведите тему:",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
        await state.set_state(ContentStates.ai_series)
        return
        
    if data.startswith("publish_"):
        await handle_publish(callback, state)
        return
    
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
    await message.answer(
        f"✅ Фото {count}!\n\nТеперь введите тему поста:",
        reply_markup=get_photo_done_keyboard()
    )


@content_router.callback_query(ContentStates.ai_photo, F.data == "ai_photo_done")
async def ai_photo_done(callback: CallbackQuery, state: FSMContext):
    """Фото готовы"""
    await callback.message.edit_text(
        "🎨 ИИ создаёт варианты...",
        reply_markup=get_back_btn()
    )
    
    data = await state.get_data()
    topic = data.get("topic", "перепланировка")
    photos = data.get("user_state", {}).get("photos", [])
    
    hooks = await viral_hooks_agent.generate_hooks(topic, count=5)
    
    variants = []
    for hook in hooks:
        text = f"{hook['text']}\n\n💡 Обращайтесь: @Parkhovenko_i_kompaniya_bot"
        variants.append({
            "type": hook.get("category", "экспертный"),
            "text": text,
            "topic": topic,
            "photos": photos
        })
    
    user_state = data.get("user_state", {})
    user_state["variants"] = variants
    await state.update_data(user_state=user_state)
    
    for i, v in enumerate(variants, 1):
        preview = v["text"][:200] + "..."
        builder = InlineKeyboardBuilder()
        builder.button(text=f"✅ Выбрать {i}", callback_data=f"select_variant_{i}")
        await callback.message.answer(
            f"📝 <b>Вариант {i}: {v['type']}</b>\n\n{preview}",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    
    await callback.message.answer(
        "Выберите вариант:",
        reply_markup=get_back_btn()
    )
    await state.set_state(ContentStates.select_variant)


# === AI TEXT ===
@content_router.message(ContentStates.ai_text)
async def ai_text_handler(message: Message, state: FSMContext):
    """Текст → пост"""
    topic = message.text
    await state.update_data(topic=topic)
    
    hooks = await viral_hooks_agent.generate_hooks(topic, count=1)
    hook = hooks[0] if hooks else {"text": f"📢 {topic}"}
    
    text = f"<b>{hook['text']}</b>\n\n💡 @Parkhovenko_i_kompaniya_bot"
    
    post_id = await db.add_content_post(
        title=topic,
        body=text,
        cta="Записаться: @Parkhovenko_i_kompaniya_bot",
        channel="draft"
    )
    
    await message.answer(
        f"📝 <b>Пост готов!</b>\n\n{text}",
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
    
    for item in chain:
        await db.add_content_post(
            title=item["topic"],
            body=item["text"],
            cta="@Parkhovenko_i_kompaniya_bot",
            channel="draft",
            scheduled_date=item.get("date")
        )
    
    text = f"📅 <b>Серия на {days} дней готова!</b>\n\n"
    for item in chain[:5]:
        text += f"📌 День {item['day']}: {item['topic']}\n"
    
    await message.answer(text, reply_markup=get_back_btn(), parse_mode="HTML")


def generate_series_chain(topic: str, days: int):
    """Генерирует цепочку постов"""
    chain = []
    themes = [
        ("Боль", f"😱 Штрафы за {topic.lower()}"),
        ("Эксперт", f"📋 Что можно при {topic.lower()}"),
        ("Эксперт", f"📁 Документы для {topic.lower()}"),
        ("Соцдок", f"🏠 Наши кейсы"),
        ("Соцдок", f"⭐ Отзывы"),
        ("CTA", f"🎯 Записаться"),
    ]
    
    for i, (theme, text_template) in enumerate(themes[:days], 1):
        hook_text = text_template.format(topic=topic)
        text = f"<b>{hook_text}</b>\n\n💡 @Parkhovenko_i_kompaniya_bot"
        chain.append({"day": i, "theme": theme, "topic": hook_text, "text": text})
    
    return chain


# === PUBLISH ===
async def handle_publish(callback: CallbackQuery, state: FSMContext):
    """Публикация"""
    data = callback.data
    parts = data.split("_")
    if len(parts) < 3:
        await callback.answer("Ошибка!")
        return
    
    channel = parts[1]
    post_id = int(parts[2])
    post = await db.get_content_post(post_id)
    
    if not post:
        await callback.answer("Пост не найден!")
        return
    
    channel_id = CHANNEL_ID if channel == "terion" else DOM_GRAND_CHANNEL_ID
    
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
        
        await db.update_content_post(post_id, status="published")
        await callback.answer("✅ Опубликовано!")
    except Exception as e:
        logger.error(f"Publish error: {e}")
        await callback.answer(f"❌ Ошибка: {e}")


(message: Message, state: FSMContext):
    """Эхо"""
    current_state = await state.get_state()
    await message.answer(f"DEBUG: state={current_state}")
