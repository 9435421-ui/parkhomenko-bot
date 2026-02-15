"""
Главное меню - старт квиза
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
import logging

from keyboards.main_menu import get_main_menu, get_admin_menu, get_urgent_btn, get_content_menu
from handlers.quiz import QuizStates
from config import ADMIN_ID
from database import db
from agents.creative_agent import creative_agent
from services.publisher import publisher
from services.image_generator import image_generator

logger = logging.getLogger(__name__)
router = Router()

GREETING_TEXT = (
    "🏢 <b>Вас приветствует компания ТЕРИОН!</b>\n\n"
    "Я — Антон, ваш ИИ-помощник по перепланировкам.\n\n"
    "Нажимая кнопку ниже, вы даете согласие на обработку "
    "персональных данных, получение уведомлений и информационную переписку.\n\n"
    "📞 Все консультации носят информационный характер, "
    "финальное решение подтверждает эксперт ТЕРИОН."
)


def _get_start_arg(text: str) -> str | None:
    """Параметр из /start (например: /start quiz → quiz)."""
    if not text or not text.strip().startswith("/start"):
        return None
    parts = text.strip().split(maxsplit=1)
    return parts[1].strip().lower() if len(parts) > 1 else None


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext):
    """Старт: по ссылке с ?start=quiz сразу запускаем квиз, иначе — приветствие/меню."""
    user_id = message.from_user.id
    start_arg = _get_start_arg(message.text or "")
    logger.info(f"📨 /start от: {user_id}, arg={start_arg!r}")
    
    await state.clear()
    
    # Ссылка из канала/поста: t.me/Bot?start=quiz → сначала согласие с ПД
    if start_arg == "quiz":
        await state.set_state(QuizStates.consent_pdp)
        from handlers.quiz import get_consent_keyboard
        await message.answer(
            "📋 <b>Перед началом необходимо ваше согласие</b>\n\n"
            "Нажимая кнопку ниже, вы даёте согласие на:\n"
            "• обработку персональных данных;\n"
            "• получение уведомлений и информационную переписку.\n\n"
            "После этого мы запросим контакт для связи.",
            reply_markup=get_consent_keyboard(),
            parse_mode="HTML"
        )
        return
    
    if str(user_id) == str(ADMIN_ID):
        await message.answer(
            "🎯 <b>Главное меню</b>\n\n"
            "🛠 <b>Создать пост</b> — Текст → Фото → Публикация\n"
            "🕵️‍♂️ <b>Темы от Шпиона</b> — CreativeAgent ищет идеи\n"
            "📅 <b>Очередь постов</b> — что запланировано на 12:00\n\n"
            "Выберите:",
            reply_markup=get_admin_menu()
        )
    else:
        await message.answer(
            GREETING_TEXT,
            reply_markup=get_main_menu(user_id)
        )


@router.message(F.text == "🛠 Создать пост")
async def create_post_handler(message: Message, state: FSMContext):
    """Создание поста: Текст, Фото, ИИ-Визуал. Публикация — TERION / ДОМ ГРАНД / MAX."""
    await message.answer(
        "🛠 <b>Создание поста</b>\n\n"
        "Выберите формат (публикация в каналы — под превью):",
        reply_markup=get_content_menu()
    )


@router.callback_query(F.data.in_(["back_to_menu", "content_back"]))
async def content_back_handler(callback: CallbackQuery, state: FSMContext):
    """Назад из меню контента — в главное меню админа"""
    await state.clear()
    if str(callback.from_user.id) == str(ADMIN_ID):
        await callback.message.edit_text(
            "🎯 <b>Главное меню</b>\n\n"
            "🛠 Создать пост — Текст / Фото / ИИ-Визуал → публикация TERION, ДОМ ГРАНД, MAX\n"
            "🕵️‍♂️ Темы от Шпиона\n"
            "📅 Очередь постов\n\n"
            "Выберите кнопку ниже:"
        )
    await callback.answer()


@router.message(F.text == "🕵️‍♂️ Темы от Шпиона")
async def spy_topics_handler(message: Message, state: FSMContext):
    """Темы от Шпиона - CreativeAgent"""
    await message.answer("🔍 <b>Шпион ищет трендовые темы...</b>", parse_mode="HTML")
    
    try:
        topics = await creative_agent.scout_topics(count=3)
        # Сохраняем темы в состояние для последующего использования
        await state.update_data(scout_topics=topics)
        
        text = "🕵️‍♂️ <b>Темы от Шпиона</b>\n\n"
        buttons = []
        for i, topic in enumerate(topics, 1):
            text += f"{i}. <b>{topic['title']}</b>\n"
            text += f"   💡 {topic['insight']}\n\n"
            
            buttons.append([
                InlineKeyboardButton(text=f"🖼 Обложка #{i}", callback_data=f"gen_img_{i}"),
                InlineKeyboardButton(text=f"📢 Опубликовать #{i}", callback_data=f"pub_topic_{i}")
            ])
        
        buttons.append([InlineKeyboardButton(text="🔄 Новые темы", callback_data="refresh_spy")])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error in spy_topics_handler: {e}")
        await message.answer(f"❌ Ошибка: {e}")

@router.callback_query(F.data == "refresh_spy")
async def refresh_spy_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer("🔄 Обновляю темы...")
    await spy_topics_handler(callback.message, state)

@router.callback_query(F.data.startswith("gen_img_"))
async def generate_image_handler(callback: CallbackQuery, state: FSMContext):
    topic_idx = int(callback.data.split("_")[-1]) - 1
    data = await state.get_data()
    topics = data.get("scout_topics", [])
    
    if topic_idx >= len(topics):
        await callback.answer("❌ Тема не найдена")
        return
        
    topic = topics[topic_idx]
    await callback.answer("🎨 Генерирую обложку...")
    
    image_bytes = await image_generator.generate_from_topic(topic)
    if image_bytes:
        photo = BufferedInputFile(image_bytes, filename="cover.jpg")
        await callback.message.answer_photo(
            photo=photo,
            caption=f"🖼 Обложка для темы:\n<b>{topic['title']}</b>",
            parse_mode="HTML"
        )
    else:
        await callback.message.answer("❌ Не удалось сгенерировать обложку")

@router.callback_query(F.data.startswith("pub_topic_"))
async def publish_topic_handler(callback: CallbackQuery, state: FSMContext):
    topic_idx = int(callback.data.split("_")[-1]) - 1
    data = await state.get_data()
    topics = data.get("scout_topics", [])
    
    if topic_idx >= len(topics):
        await callback.answer("❌ Тема не найдена")
        return
        
    topic = topics[topic_idx]
    await callback.answer("📢 Публикую...")
    
    # Генерируем обложку перед публикацией
    image_bytes = await image_generator.generate_from_topic(topic)
    
    post_text = f"📌 <b>{topic['title']}</b>\n\n{topic['insight']}\n\n#перепланировка #согласование #терион"
    
    results = await publisher.publish_all(post_text, image_bytes)
    
    success_count = sum(1 for r in results.values() if r)
    total_count = len(results)
    
    await callback.message.answer(
        f"✅ <b>Публикация завершена!</b>\n"
        f"Успешно: {success_count}/{total_count}\n"
        f"Каналы: {', '.join(results.keys())}",
        parse_mode="HTML"
    )


@router.message(F.text == "📅 Очередь постов")
async def queue_handler(message: Message, state: FSMContext):
    """Очередь постов"""
    await message.answer("📅 <b>Очередь постов</b>\n\nЗагрузка...", parse_mode="HTML")
    
    try:
        posts = await db.get_draft_posts()
        
        if not posts:
            await message.answer("📭 Очередь пуста. Создайте первый пост!", parse_mode="HTML")
            return
        
        text = "📅 <b>Очередь постов</b>\n\n"
        for post in posts[-10:]:
            status = "⏳" if post.get("status") == "draft" else "📤"
            topic = post.get("title", "Без темы")
            text += f"{status} #{post.get('id', '?')} — {topic}\n"
        
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(lambda m: m.text and m.text.startswith("Срочно:"))
async def urgent_handler(message: Message, state: FSMContext):
    """Обработка срочных сообщений от Юлии"""
    user_id = message.from_user.id
    logger.info(f"🚀 Срочно от: {user_id}")
    
    if str(user_id) != str(ADMIN_ID):
        return
    
    text = message.text.replace("Срочно:", "").strip()
    
    await message.answer(
        f"🚀 <b>Срочная публикация!</b>\n\n"
        f"<b>Текст:</b>\n{text}\n\n"
        f"Опубликовать сейчас вне очереди?",
        reply_markup=get_urgent_btn(),
        parse_mode="HTML"
    )


@router.message(F.text == "📝 Записаться на консультацию")
async def quiz_start(message: Message, state: FSMContext):
    """Запуск квиза: сначала согласие с ПД, затем контакт"""
    await state.clear()
    from handlers.quiz import get_consent_keyboard
    await state.set_state(QuizStates.consent_pdp)
    await message.answer(
        "📋 <b>Перед началом необходимо ваше согласие</b>\n\n"
        "Нажимая кнопку ниже, вы даёте согласие на:\n"
        "• обработку персональных данных;\n"
        "• получение уведомлений и информационную переписку.\n\n"
        "После этого мы запросим контакт для связи.",
        reply_markup=get_consent_keyboard(),
        parse_mode="HTML"
    )


@router.message(F.text == "💬 Задать вопрос")
async def question_handler(message: Message, state: FSMContext):
    """Задать вопрос консультанту"""
    await message.answer(
        "💬 <b>Задайте ваш вопрос</b>\n\n"
        "Наш ИИ-консультант ответит на основе базы знаний "
        "по перепланировкам и согласованию.",
        parse_mode="HTML"
    )


# === CALLBACK HANDLERS ===
@router.callback_query(F.data == "content_back")
async def content_back_handler(callback: CallbackQuery, state: FSMContext):
    """Назад в меню"""
    await state.clear()
    await callback.message.edit_text(
        "📝 <b>Создание поста</b>\n\n"
        "Выберите формат:",
        reply_markup=get_content_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "menu:create")
async def menu_create_handler(callback: CallbackQuery, state: FSMContext):
    """Меню: Создать пост"""
    await callback.message.edit_text(
        "🎨 <b>Генерация поста</b>\n\n"
        "Введите тему поста:",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "menu:editor")
async def menu_editor_handler(callback: CallbackQuery, state: FSMContext):
    """Меню: Редактор текста"""
    await callback.message.edit_text(
        "✍️ <b>Редактор текста</b>\n\n"
        "Введите текст для публикации:",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "menu:photo")
async def menu_photo_handler(callback: CallbackQuery, state: FSMContext):
    """Меню: Пост по фото"""
    await callback.message.edit_text(
        "📸 <b>Пост по фото</b>\n\n"
        "Загрузите фото объекта:",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "urgent_publish")
async def urgent_publish_handler(callback: CallbackQuery, state: FSMContext):
    """Срочная публикация"""
    await callback.message.edit_text(
        "🚀 <b>Срочная публикация отправлена!</b>\n\n"
        "Пост опубликован вне очереди.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "urgent_edit")
async def urgent_edit_handler(callback: CallbackQuery, state: FSMContext):
    """Доработка срочного поста"""
    await callback.message.edit_text(
        "📝 <b>Доработка поста</b>\n\n"
        "Введите исправленный текст:",
        parse_mode="HTML"
    )
    await callback.answer()
