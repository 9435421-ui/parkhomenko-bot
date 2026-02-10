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
from config import CHANNEL_ID_TERION, CHANNEL_ID_DOM_GRAD, VK_GROUP_ID, LEADS_GROUP_CHAT_ID, THREAD_ID_NEWS, THREAD_ID_CONTENT_PLAN
from services.vk_service import vk_service

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


# === KEYBOARDS ===
def get_content_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Создать пост", callback_data="menu:create")
    builder.button(text="🗓 Контент-план", callback_data="menu:plan")
    builder.button(text="📸 Пост по фото", callback_data="menu:photo")
    builder.button(text="✍️ Редактор текста", callback_data="menu:editor")
    builder.button(text="📰 Новости отрасли", callback_data="menu:news")
    return builder.as_markup()


def get_back_btn() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ В меню", callback_data="content_back")
    return builder.as_markup()


def get_publish_btns(post_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📤 TERION", callback_data=f"publish_terion_{post_id}")
    builder.button(text="📤 ДОМ ГРАНД", callback_data=f"publish_dom_{post_id}")
    builder.button(text="📤 ВК", callback_data=f"publish_vk_{post_id}")
    builder.button(text="◀️ В меню", callback_data="content_back")
    return builder.as_markup()


def get_photo_done_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Хватит фото", callback_data="ai_photo_done")
    builder.button(text="◀️ В меню", callback_data="content_back")
    return builder.as_markup()


# === /START ===
@content_router.message(CommandStart())
async def content_start(message: Message, state: FSMContext):
    """Старт Content Bot"""
    await state.clear()
    await message.answer(
        "🎯 <b>Content Bot</b>\n\nВыберите:",
        reply_markup=get_content_menu(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.main_menu)


# === CALLBACKS ===
@content_router.callback_query(F.data.startswith("menu:"))
async def content_callback(callback: CallbackQuery, state: FSMContext):
    data = callback.data
    
    if data == "content_back":
        await callback.message.edit_text(
            "🎯 <b>Content Bot</b>\n\nВыберите:",
            reply_markup=get_content_menu(),
            parse_mode="HTML"
        )
        await state.set_state(ContentStates.main_menu)
        return
    
    if data == "menu:create":
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
    
    if data == "menu:photo":
        await state.update_data(user_state={"step": "ai_photo_wait_photo"})
        await callback.message.edit_text(
            "📸 <b>Фото + ИИ-пост</b>\n\nЗагрузите фото объекта:",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
        await state.set_state(ContentStates.ai_photo)
        return
        
    if data == "menu:editor":
        await state.update_data(user_state={"step": "ai_text_wait_topic"})
        await callback.message.edit_text(
            "📝 <b>Только текст</b>\n\nВведите тему поста:",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
        await state.set_state(ContentStates.ai_text)
        return
        
    if data == "menu:plan":
        builder = InlineKeyboardBuilder()
        builder.button(text="7 дней", callback_data="menu:series_7")
        builder.button(text="14 дней", callback_data="menu:series_14")
        builder.button(text="30 дней", callback_data="menu:series_30")
        builder.adjust(3)
        
        await callback.message.edit_text(
            "📅 <b>Серия постов</b>\n\nВыберите длительность:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        await state.set_state(ContentStates.ai_series)
        return
        
    if data.startswith("menu:series_"):
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
        text = f"{hook['text']}\n\n💡 @Parkhovenko_i_kompaniya_bot"
        variants.append({"type": hook.get("category", "экспертный"), "text": text, "topic": topic, "photos": photos})
    
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
    
    await callback.message.answer("Выберите вариант:", reply_markup=get_back_btn())
    await state.set_state(ContentStates.select_variant)


# === AI TEXT ===
@content_router.message(ContentStates.ai_text)
async def ai_text_handler(message: Message, state: FSMContext):
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
    
    # Выбираем канал
    if channel == "terion":
        channel_id = CHANNEL_ID_TERION
        channel_name = "TERION"
    elif channel == "dom":
        channel_id = CHANNEL_ID_DOM_GRAD
        channel_name = "ДОМ ГРАНД"
    elif channel == "vk":
        # Публикуем в ВК
        vk_result = await vk_service.post(post["body"])
        if vk_result:
            await db.update_content_post(post_id, status="published")
            await callback.message.edit_text(
                "✅ <b>Опубликовано ВКонтакте!</b>\n\n"
                f"Пост #{vk_result}",
                reply_markup=get_content_menu(),
                parse_mode="HTML"
            )
        else:
            await callback.answer("❌ Ошибка ВК!")
        return
    else:
        await callback.answer("Неизвестный канал!")
        return
    
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
        await callback.message.edit_text(
            f"✅ <b>Опубликовано в {channel_name}!</b>",
            reply_markup=get_content_menu(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Publish error: {e}")
        await callback.answer(f"❌ Ошибка: {e}")


@content_router.callback_query(F.data == "menu:news")
async def show_news(callback: CallbackQuery, state: FSMContext):
    """Показывает новости от ScoutAgent и отправляет в топик 780"""
    await callback.message.edit_text(
        "📰 <b>Новости отрасли</b>\n\n🔍 Ищем актуальные новости...",
        parse_mode="HTML"
    )
    
    try:
        topics = await scout_agent.scout_topics(count=5)
        
        if not topics:
            await callback.message.edit_text(
                "📰 <b>Новости</b>\n\nНе удалось найти новости.",
                reply_markup=get_back_btn(),
                parse_mode="HTML"
            )
            await callback.answer()
            return
        
        text = "📰 <b>Актуальные новости</b>\n\n"
        
        for i, topic in enumerate(topics, 1):
            title = topic.get("title", "Новость")[:50]
            insight = topic.get("insight", "")[:80]
            text += f"{i}. <b>{title}</b>\n   💡 {insight}\n\n"
            await state.update_data({f"news_{i}": topic})
        
        # Отправляем в топик НОВОСТИ (780)
        await callback.bot.send_message(
            chat_id=LEADS_GROUP_CHAT_ID,
            message_thread_id=THREAD_ID_NEWS,
            text=f"📰 <b>Новости от ScoutAgent</b>\n\n{text}",
            parse_mode="HTML"
        )
        
        builder = InlineKeyboardBuilder()
        for i, topic in enumerate(topics[:5], 1):
            builder.button(text=f"📝 Пост из новости {i}", callback_data=f"news:{i}")
        builder.button(text="◀️ В меню", callback_data="content_back")
        
        await callback.message.edit_text(
            text + "📝 Нажмите на кнопку для создания поста.",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"News error: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
    
    await callback.answer()


@content_router.callback_query(F.data.startswith("menu:news:"))
async def generate_post_from_news(callback: CallbackQuery, state: FSMContext):
    """Генерирует пост из новости"""
    news_id = int(callback.data.replace("news:", ""))
    
    await callback.message.edit_text(
        "📝 <b>Создание поста из новости</b>\n\n🎨 Генерирую...",
        parse_mode="HTML"
    )
    
    try:
        data = await state.get_data()
        topic = data.get(f"news_{news_id}", {})
        
        title = topic.get("title", "Новость")
        insight = topic.get("insight", "")
        
        hooks = await viral_hooks_agent.generate_hooks(title, count=1)
        hook = hooks[0] if hooks else {"text": f"📰 {title}"}
        
        text = f"<b>{hook['text']}</b>\n\n💡 {insight}\n\n📚 Читайте подробности!\n💡 @Parkhovenko_i_kompaniya_bot"
        
        post_id = await db.add_content_post(
            title=title,
            body=text,
            cta="Записаться: @Parkhovenko_i_kompaniya_bot",
            channel="draft"
        )
        
        await state.update_data({"post_id": post_id})
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📤 Опубликовать", callback_data=f"publish:dom:{post_id}")
        builder.button(text="◀️ В меню", callback_data="content_back")
        
        await callback.message.edit_text(
            f"✨ <b>Пост готов!</b>\n\n{text}\n\n",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Generate from news error: {e}")
        await callback.message.edit_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
    
    await callback.answer()


@content_router.callback_query(F.data == "menu:plan")
async def show_content_plan(callback: CallbackQuery, state: FSMContext, days: int = 7):
    """Генерирует контент-план и отправляет в топик 83"""
    text = f"🗓 <b>Контент-план на {days} дней</b>\n\n"
    
    topics = await scout_agent.scout_topics(count=days)
    rubrics = ["💡 Полезный", "📊 Кейс", "🔥 Акция", "❤️ Эмоция"]
    
    for i, topic in enumerate(topics, 1):
        rubric = rubrics[i % len(rubrics)]
        title = topic.get("title", "")[:30]
        insight = topic.get("insight", "")[:40]
        text += f"{i} | {rubric} | {title} | {insight}\n"
    
    # Отправляем в топик КОНТЕНТ-ПЛАН (83)
    await callback.bot.send_message(
        chat_id=LEADS_GROUP_CHAT_ID,
        message_thread_id=THREAD_ID_CONTENT_PLAN,
        text=text,
        parse_mode="HTML"
    )
    
    await callback.message.edit_text(
        f"{text}\n\n✅ Отправлено в рабочую группу!",
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )


# === ScoutAgent заглушка ===
try:
    from agents.scout_agent import scout_agent
except ImportError:
    class DummyScout:
        async def scout_topics(self, count=3):
            return [{"title": f"Тема {i}", "insight": "Актуальная информация"} for i in range(1, count+1)]
    scout_agent = DummyScout()
