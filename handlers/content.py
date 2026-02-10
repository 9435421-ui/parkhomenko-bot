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
from content_agent import ContentAgent
from image_gen import generate
from config import (
    CHANNEL_ID_TERION, 
    CHANNEL_ID_DOM_GRAD, 
    VK_GROUP_ID, 
    LEADS_GROUP_CHAT_ID, 
    THREAD_ID_NEWS, 
    THREAD_ID_CONTENT_PLAN,
    THREAD_ID_DRAFTS,
    THREAD_ID_LOGS,
    THREAD_ID_HOT_LEADS
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


def get_publish_btns(post_id: int, include_image: bool = False) -> InlineKeyboardMarkup:
    """Кнопки публикации — формат publish:{channel}:{id}"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📤 TERION", callback_data=f"publish:terion:{post_id}")
    builder.button(text="📤 ДОМ ГРАНД", callback_data=f"publish:dom:{post_id}")
    builder.button(text="📤 ВК", callback_data=f"publish:vk:{post_id}")
    builder.button(text="📤 Max", callback_data=f"publish:max:{post_id}")
    
    # Кнопка публикации ВЕЗДЕ
    builder.button(text="🚀 Опубликовать ВЕЗДЕ", callback_data=f"publish_all:{post_id}")
    
    # Кнопка генерации изображения
    if not include_image:
        builder.button(text="🎨 Сгенерировать ИИ-фото", callback_data=f"gen_image:{post_id}")
    
    builder.button(text="◀️ В меню", callback_data="content_back")
    builder.adjust(4, 1, 1, 1)
    return builder.as_markup()


def get_photo_done_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Хватит фото", callback_data="ai_photo_done")
    builder.button(text="◀️ В меню", callback_data="content_back")
    return builder.as_markup()


def get_plan_days_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="7 дней", callback_data="plan_days_7")
    builder.button(text="14 дней", callback_data="plan_days_14")
    builder.button(text="30 дней", callback_data="plan_days_30")
    builder.adjust(3)
    return builder.as_markup()


# === /START ===
@content_router.message(CommandStart())
async def content_start(message: Message, state: FSMContext):
    """Старт Content Bot"""
    await state.clear()
    await message.answer("🎯 <b>Content Bot</b>\n\nВыберите:", reply_markup=get_content_menu(), parse_mode="HTML")
    await state.set_state(ContentStates.main_menu)


# === NAVIGATION ===
@content_router.callback_query(F.data == "content_back")
async def content_back(callback: CallbackQuery, state: FSMContext):
    """Назад в главное меню"""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("🎯 <b>Content Bot</b>\n\nВыберите:", reply_markup=get_content_menu(), parse_mode="HTML")
    await state.set_state(ContentStates.main_menu)


# === MENU: CREATE ===
@content_router.callback_query(F.data == "menu:create")
async def menu_create(callback: CallbackQuery, state: FSMContext):
    """Меню: Создать пост"""
    await callback.answer()
    builder = InlineKeyboardBuilder()
    builder.button(text="📸 Фото + ИИ-пост", callback_data="menu:photo")
    builder.button(text="📝 Только текст", callback_data="menu:editor")
    builder.button(text="📅 Серия постов", callback_data="menu:series")
    builder.adjust(1)
    await callback.message.edit_text("📝 <b>Создание поста</b>\n\nВыберите формат:", reply_markup=builder.as_markup(), parse_mode="HTML")


# === MENU: PHOTO ===
@content_router.callback_query(F.data == "menu:photo")
async def menu_photo(callback: CallbackQuery, state: FSMContext):
    """Меню: Пост по фото"""
    await callback.answer()
    await state.update_data(user_state={"step": "ai_photo_wait_photo"})
    await callback.message.edit_text("📸 <b>Фото + ИИ-пост</b>\n\nЗагрузите фото объекта:", reply_markup=get_back_btn(), parse_mode="HTML")
    await state.set_state(ContentStates.ai_photo)


# === MENU: EDITOR ===
@content_router.callback_query(F.data == "menu:editor")
async def menu_editor(callback: CallbackQuery, state: FSMContext):
    """Меню: Редактор текста"""
    await callback.answer()
    await state.update_data(user_state={"step": "ai_text_wait_topic"})
    await callback.message.edit_text("📝 <b>Только текст</b>\n\nВведите тему поста:", reply_markup=get_back_btn(), parse_mode="HTML")
    await state.set_state(ContentStates.ai_text)


# === MENU: SERIES ===
@content_router.callback_query(F.data == "menu:series")
async def menu_series(callback: CallbackQuery, state: FSMContext):
    """Меню: Серия постов"""
    await callback.answer()
    await callback.message.edit_text("📅 <b>Серия постов</b>\n\nВыберите длительность:", reply_markup=get_plan_days_keyboard(), parse_mode="HTML")
    await state.set_state(ContentStates.ai_series)


# === MENU: PLAN DAYS ===
@content_router.callback_query(F.data.startswith("plan_days_"))
async def menu_plan_days(callback: CallbackQuery, state: FSMContext):
    """Выбор длительности плана"""
    await callback.answer()
    days = int(callback.data.split("_")[-1])
    user_state = {"step": "series_wait_topic", "days": days}
    await state.update_data(user_state=user_state)
    await callback.message.edit_text(f"📅 <b>Серия на {days} дней</b>\n\nВведите тему:", reply_markup=get_back_btn(), parse_mode="HTML")


# === MENU: PLAN ===
@content_router.callback_query(F.data == "menu:plan")
async def menu_plan(callback: CallbackQuery, state: FSMContext):
    """Меню: Контент-план"""
    await callback.answer()
    await show_content_plan(callback, state, days=7)


# === MENU: NEWS ===
@content_router.callback_query(F.data == "menu:news")
async def menu_news(callback: CallbackQuery, state: FSMContext):
    """Меню: Новости отрасли"""
    await callback.answer()
    await callback.message.edit_text("📰 <b>Новости отрасли</b>\n\n🔍 Ищем актуальные новости...", parse_mode="HTML")
    
    try:
        topics = await scout_agent.scout_topics(count=5)
        
        if not topics:
            await callback.message.edit_text("📰 <b>Новости</b>\n\nНе удалось найти новости.", reply_markup=get_back_btn(), parse_mode="HTML")
            return
        
        text = "📰 <b>Актуальные новости</b>\n\n"
        
        for i, topic in enumerate(topics, 1):
            title = topic.get("title", "Новость")[:50]
            insight = topic.get("insight", "")[:80]
            text += f"{i}. <b>{title}</b>\n   💡 {insight}\n\n"
            await state.update_data({f"news_{i}": topic})
        
        await callback.bot.send_message(chat_id=LEADS_GROUP_CHAT_ID, message_thread_id=THREAD_ID_NEWS, text=f"📰 <b>Новости от ScoutAgent</b>\n\n{text}", parse_mode="HTML")
        
        builder = InlineKeyboardBuilder()
        for i, topic in enumerate(topics[:5], 1):
            builder.button(text=f"📝 Пост из новости {i}", callback_data=f"menu:news:{i}")
        builder.button(text="◀️ В меню", callback_data="content_back")
        
        await callback.message.edit_text(text + "📝 Нажмите на кнопку для создания поста.", reply_markup=builder.as_markup(), parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"News error: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {e}", reply_markup=get_back_btn(), parse_mode="HTML")


# === MENU: NEWS DETAIL ===
@content_router.callback_query(F.data.startswith("menu:news:"))
async def menu_news_detail(callback: CallbackQuery, state: FSMContext):
    """Генерирует пост из новости С АВТО-ГЕНЕРАЦИЕЙ КАРТИНКИ"""
    await callback.answer()
    news_id = int(callback.data.replace("menu:news:", ""))
    
    await callback.message.edit_text("📝 <b>Создание поста из новости</b>\n\n🎨 Генерируем пост и картинку...", parse_mode="HTML")
    
    try:
        data = await state.get_data()
        topic = data.get(f"news_{news_id}", {})
        
        title = topic.get("title", "Новость")
        insight = topic.get("insight", "")
        
        hooks = await viral_hooks_agent.generate_hooks(title, count=1)
        hook = hooks[0] if hooks else {"text": f"📰 {title}"}
        
        text = f"<b>{hook['text']}</b>\n\n💡 {insight}\n\n📚 Читайте подробности!\n💡 @Parkhovenko_i_kompaniya_bot"
        
        post_id = await db.add_content_post(title=title, body=text, cta="Записаться: @Parkhovenko_i_kompaniya_bot", channel="draft")
        await state.update_data({"post_id": post_id})
        
        # АВТО-генерация картинки с try/except
        await callback.message.edit_text("🎨 <b>Генерируем изображение...</b>", parse_mode="HTML")
        
        try:
            image_url = await content_agent.generate_image(prompt=title)
        except Exception as e:
            logger.error(f"Image gen error: {e}")
            image_url = None
        
        if image_url:
            await db.update_content_post(post_id, image_url=image_url)
            await callback.message.answer_photo(
                photo=image_url,
                caption=f"✨ <b>Пост готов!</b>\n\n{text}",
                reply_markup=get_publish_btns(post_id),
                parse_mode="HTML"
            )
        else:
            # Placeholder если картинка недоступна
            placeholder = "https://via.placeholder.com/1024x1024.png?text=Новость+ TERION"
            await db.update_content_post(post_id, image_url=placeholder)
            await callback.message.answer_photo(
                photo=placeholder,
                caption=f"✨ <b>Пост готов!</b>\n\n{text}",
                reply_markup=get_publish_btns(post_id),
                parse_mode="HTML"
            )
        
    except Exception as e:
        logger.error(f"Generate from news error: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {e}", reply_markup=get_back_btn(), parse_mode="HTML")


# === PUBLISH ===
@content_router.callback_query(F.data.startswith("publish:"))
async def menu_publish(callback: CallbackQuery, state: FSMContext):
    """Публикация поста"""
    await callback.answer()
    await handle_publish(callback, state)


# === PUBLISH ALL (EVERYWHERE) ===
@content_router.callback_query(F.data.startswith("publish_all:"))
async def publish_all_handler(callback: CallbackQuery, state: FSMContext):
    """Публикация поста ВЕЗДЕ: TG + VK + Max"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    if not post:
        await callback.answer("❌ Пост не найден")
        return
    
    await callback.message.edit_text("🚀 <b>Публикую ВЕЗДЕ!</b>\n\nTG → VK → Max", parse_mode="HTML")
    
    results = []
    
    # 1. TERION
    try:
        if post.get("image_url"):
            await callback.bot.send_photo(chat_id=CHANNEL_ID_TERION, photo=post["image_url"], caption=post["body"], parse_mode="HTML")
        else:
            await callback.bot.send_message(chat_id=CHANNEL_ID_TERION, text=post["body"], parse_mode="HTML")
        results.append("✅ TERION")
    except Exception as e:
        logger.error(f"TERION publish error: {e}")
        results.append("❌ TERION")
    
    # 2. ДОМ ГРАНД
    try:
        if post.get("image_url"):
            await callback.bot.send_photo(chat_id=CHANNEL_ID_DOM_GRAD, photo=post["image_url"], caption=post["body"], parse_mode="HTML")
        else:
            await callback.bot.send_message(chat_id=CHANNEL_ID_DOM_GRAD, text=post["body"], parse_mode="HTML")
        results.append("✅ ДОМ ГРАНД")
    except Exception as e:
        logger.error(f"DOM_GRAD publish error: {e}")
        results.append("❌ ДОМ ГРАНД")
    
    # 3. ВКонтакте (с CTA квиза)
    try:
        vk_result = await vk_service.post_with_quiz_cta(post["body"])
        if vk_result:
            results.append(f"✅ ВК (#{vk_result})")
        else:
            results.append("❌ ВК")
    except Exception as e:
        logger.error(f"VK publish error: {e}")
        results.append("❌ ВК")
    
    # 4. Max.ru
    try:
        max_result = await content_agent.post_to_max(post_id)
        if max_result:
            results.append("✅ Max.ru")
        else:
            results.append("❌ Max.ru")
    except Exception as e:
        logger.error(f"Max publish error: {e}")
        results.append("❌ Max.ru")
    
    # Обновляем статус
    await db.update_content_post(post_id, status="published")
    
    # Результат
    result_text = "🚀 <b>Публикация завершена!</b>\n\n" + "\n".join(results)
    await callback.message.edit_text(result_text, reply_markup=get_content_menu(), parse_mode="HTML")


# === GENERATE IMAGE ===
@content_router.callback_query(F.data.startswith("gen_image:"))
async def generate_image_handler(callback: CallbackQuery):
    """Генерация изображения Flux для поста с try/except"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    if not post:
        await callback.answer("❌ Пост не найден")
        return
    
    await callback.message.edit_text("🎨 <b>Flux создаёт шедевр...</b>\nЭто займет около 15-20 секунд.", parse_mode="HTML")
    
    # Безопасная генерация изображения
    try:
        image_url = await content_agent.generate_image(prompt=post['title'])
    except Exception as e:
        logger.error(f"Image gen error: {e}")
        image_url = None
    
    if image_url:
        await db.update_content_post(post_id, image_url=image_url)
        await callback.message.answer_photo(
            photo=image_url,
            caption=f"✨ Изображение готово для поста: <b>{post['title']}</b>",
            reply_markup=get_publish_btns(post_id),
            parse_mode="HTML"
        )
    else:
        # Картинка недоступна - показываем fallback с кнопками
        await callback.message.edit_text(
            f"🎨 <b>Картинка временно недоступна</b>\n\n"
            f"Но ваш пост готов!\n\n"
            f"<b>{post['title']}</b>\n\n"
            f"📤 Выберите канал для публикации:",
            reply_markup=get_publish_btns(post_id),
            parse_mode="HTML"
        )


# === AI PHOTO ===
@content_router.message(ContentStates.ai_photo, F.photo)
async def ai_photo_handler(message: Message, state: FSMContext):
    """Обработка фото"""
    data = await state.get_data()
    user_state = data.get("user_state", {})
    photos = user_state.get("photos", [])
    
    file_id = message.photo[-1].file_id
    photos.append(file_id)
    user_state["photos"] = photos
    await state.update_data(user_state=user_state)
    
    count = len(photos)
    await message.answer(f"✅ Фото {count}!\n\nТеперь введите тему поста:", reply_markup=get_photo_done_keyboard())


@content_router.callback_query(ContentStates.ai_photo, F.data == "ai_photo_done")
async def ai_photo_done(callback: CallbackQuery, state: FSMContext):
    """Генерация вариантов из фото"""
    await callback.answer()
    await callback.message.edit_text("🎨 ИИ создаёт варианты...", reply_markup=get_back_btn())
    
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
        await callback.message.answer(f"📝 <b>Вариант {i}: {v['type']}</b>\n\n{preview}", reply_markup=builder.as_markup(), parse_mode="HTML")
    
    await callback.message.answer("Выберите вариант:", reply_markup=get_back_btn())
    await state.set_state(ContentStates.select_variant)


# === AI TEXT ===
@content_router.message(ContentStates.ai_text)
async def ai_text_handler(message: Message, state: FSMContext):
    """Генерация поста из текста"""
    topic = message.text
    await state.update_data(topic=topic)
    
    hooks = await viral_hooks_agent.generate_hooks(topic, count=1)
    hook = hooks[0] if hooks else {"text": f"📢 {topic}"}
    
    text = f"<b>{hook['text']}</b>\n\n💡 @Parkhovenko_i_kompaniya_bot"
    
    post_id = await db.add_content_post(title=topic, body=text, cta="Записаться: @Parkhovenko_i_kompaniya_bot", channel="draft")
    
    await message.answer(f"📝 <b>Пост готов!</b>\n\n{text}", reply_markup=get_publish_btns(post_id), parse_mode="HTML")


# === AI SERIES ===
@content_router.message(ContentStates.ai_series)
async def ai_series_handler(message: Message, state: FSMContext):
    """Генерация серии постов"""
    topic = message.text
    data = await state.get_data()
    days = data.get("user_state", {}).get("days", 7)
    
    chain = generate_series_chain(topic, days)
    
    for item in chain:
        await db.add_content_post(title=item["topic"], body=item["text"], cta="@Parkhovenko_i_kompaniya_bot", channel="draft", scheduled_date=item.get("date"))
    
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


async def handle_publish(callback: CallbackQuery, state: FSMContext):
    """Публикация поста в канал — формат publish:{channel}:{id}"""
    data = callback.data
    # Формат: publish:terion:123 -> ["publish", "terion", "123"]
    parts = data.split(":")
    if len(parts) < 3:
        await callback.answer("Ошибка формата!")
        return
    
    channel = parts[1]
    try:
        post_id = int(parts[2])
    except ValueError:
        await callback.answer("Ошибка ID!")
        return
    post = await db.get_content_post(post_id)
    
    if not post:
        await callback.answer("Пост не найден!")
        return
    
    if channel == "terion":
        channel_id = CHANNEL_ID_TERION
        channel_name = "TERION"
    elif channel == "dom":
        channel_id = CHANNEL_ID_DOM_GRAD
        channel_name = "ДОМ ГРАНД"
    elif channel == "vk":
        vk_result = await vk_service.post(post["body"])
        if vk_result:
            await db.update_content_post(post_id, status="published")
            await callback.message.edit_text("✅ <b>Опубликовано ВКонтакте!</b>\n\nПост #" + str(vk_result), reply_markup=get_content_menu(), parse_mode="HTML")
        else:
            await callback.answer("❌ Ошибка ВК!")
        return
    elif channel == "max":
        # Публикация в Max.ru
        await callback.message.edit_text("📤 <b>Публикую в Max.ru...</b>", parse_mode="HTML")
        max_result = await content_agent.post_to_max(post_id)
        if max_result:
            await db.update_content_post(post_id, status="published")
            await callback.message.edit_text("✅ <b>Опубликовано в Max.ru!</b>", reply_markup=get_content_menu(), parse_mode="HTML")
        else:
            await callback.answer("❌ Ошибка Max.ru!")
        return
    else:
        await callback.answer("Неизвестный канал!")
        return
    
    try:
        if post.get("image_url"):
            await callback.bot.send_photo(chat_id=channel_id, photo=post["image_url"], caption=post["body"], parse_mode="HTML")
        else:
            await callback.bot.send_message(chat_id=channel_id, text=post["body"], parse_mode="HTML")
        
        await db.update_content_post(post_id, status="published")
        await callback.message.edit_text(f"✅ <b>Опубликовано в {channel_name}!</b>", reply_markup=get_content_menu(), parse_mode="HTML")
    except Exception as e:
        logger.error(f"Publish error: {e}")
        await callback.answer(f"❌ Ошибка: {e}")


# === CONTENT PLAN ===
async def show_content_plan(callback: CallbackQuery, state: FSMContext, days: int = 7):
    """Генерирует контент-план с кнопкой генерации всех постов"""
    text = f"🗓 <b>Контент-план на {days} дней</b>\n\n"
    
    topics = await scout_agent.scout_topics(count=days)
    rubrics = ["💡 Полезный", "📊 Кейс", "🔥 Акция", "❤️ Эмоция"]
    
    for i, topic in enumerate(topics, 1):
        rubric = rubrics[i % len(rubrics)]
        title = topic.get("title", "")[:30]
        insight = topic.get("insight", "")[:40]
        text += f"{i} | {rubric} | {title} | {insight}\n"
        await state.update_data({f"plan_topic_{i}": topic})
    
    await state.update_data({"plan_days": days})
    
    # Кнопки управления планом
    builder = InlineKeyboardBuilder()
    builder.button(text="🤖 Сгенерировать все посты", callback_data="gen_all_posts")
    builder.button(text="◀️ В меню", callback_data="content_back")
    
    await callback.bot.send_message(chat_id=LEADS_GROUP_CHAT_ID, message_thread_id=THREAD_ID_CONTENT_PLAN, text=text, parse_mode="HTML")
    await callback.message.edit_text(f"{text}\n\n✅ Отправлено в рабочую группу!", reply_markup=builder.as_markup(), parse_mode="HTML")


# === GENERATE ALL POSTS FROM PLAN ===
@content_router.callback_query(F.data == "gen_all_posts")
async def generate_all_posts(callback: CallbackQuery, state: FSMContext):
    """Генерирует все посты из плана"""
    await callback.answer("🚀 Генерируем все посты...")
    
    data = await state.get_data()
    days = data.get("plan_days", 7)
    
    await callback.message.edit_text(f"🗓 <b>Генерируем {days} постов...</b>\n\n🎨 Это займёт несколько минут...", parse_mode="HTML")
    
    try:
        posts_generated = 0
        
        for i in range(1, days + 1):
            topic = data.get(f"plan_topic_{i}", {})
            title = topic.get("title", f"Пост {i}")
            
            # Генерируем пост
            hooks = await viral_hooks_agent.generate_hooks(title, count=1)
            hook = hooks[0] if hooks else {"text": f"📰 {title}"}
            
            post_text = f"<b>{hook['text']}</b>\n\n💡 {topic.get('insight', '')}\n\n👉 @Parkhovenko_i_kompaniya_bot"
            
            post_id = await db.add_content_post(
                title=title, 
                body=post_text, 
                cta="👉 @Parkhovenko_i_kompaniya_bot", 
                channel="draft"
            )
            
            # Генерируем картинку
            image_url = await content_agent.generate_image(prompt=title)
            if image_url:
                await db.update_content_post(post_id, image_url=image_url)
            
            posts_generated += 1
        
        # Отправляем черновики в рабочую группу
        draft_text = f"📝 <b>Черновики постов ({posts_generated})</b>\n\n"
        for i in range(1, posts_generated + 1):
            draft_text += f"{i}. Пост #{i} готов к публикации\n"
        
        await callback.bot.send_message(
            chat_id=LEADS_GROUP_CHAT_ID, 
            message_thread_id=THREAD_ID_DRAFTS, 
            text=draft_text,
            parse_mode="HTML"
        )
        
        await callback.message.edit_text(
            f"✅ <b>Все {posts_generated} постов сгенерированы!</b>\n\n"
            f"📝 Посты сохранены в черновики (ID {THREAD_ID_DRAFTS}).\n\n"
            f"🎨 К каждому посту сгенерировано изображение.\n\n"
            f"📤 Выберите посты для публикации.",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Generate all posts error: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {e}", reply_markup=get_back_btn(), parse_mode="HTML")


# === SELECT VARIANT ===
@content_router.callback_query(F.data.startswith("select_variant_"))
async def select_variant_handler(callback: CallbackQuery, state: FSMContext):
    """Выбор варианта поста из фото"""
    await callback.answer()
    
    variant_num = int(callback.data.replace("select_variant_", ""))
    data = await state.get_data()
    variants = data.get("user_state", {}).get("variants", [])
    
    if variant_num <= len(variants):
        variant = variants[variant_num - 1]
        
        post_id = await db.add_content_post(
            title=variant["topic"],
            body=variant["text"],
            cta="👉 @Parkhovenko_i_kompaniya_bot",
            channel="draft"
        )
        
        await callback.message.edit_text(
            f"✨ <b>Пост готов!</b>\n\n{variant['text']}",
            reply_markup=get_publish_btns(post_id),
            parse_mode="HTML"
        )
    else:
        await callback.answer("Вариант не найден")


# === URGENT HANDLERS ===
@content_router.callback_query(F.data == "urgent_publish")
async def urgent_publish(callback: CallbackQuery, state: FSMContext):
    """Срочная публикация"""
    await callback.answer()
    await callback.message.edit_text("🚀 <b>Срочная публикация!</b>\n\nПост отмечен как срочный.", parse_mode="HTML")


@content_router.callback_query(F.data == "urgent_edit")
async def urgent_edit(callback: CallbackQuery, state: FSMContext):
    """Доработка срочного поста"""
    await callback.answer()
    await callback.message.edit_text("📝 <b>Доработка поста</b>\n\nВведите исправленный текст:", parse_mode="HTML")


# === ScoutAgent Dummy ===
try:
    from agents.scout_agent import scout_agent
except ImportError:
    class DummyScout:
        async def scout_topics(self, count=3):
            return [{"title": f"Тема {i}", "insight": "Актуальная информация"} for i in range(1, count+1)]
    scout_agent = DummyScout()
