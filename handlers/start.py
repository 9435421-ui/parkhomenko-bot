import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging

from keyboards.main_menu import get_main_menu, get_admin_menu, get_urgent_btn
from handlers.quiz import QuizStates


class QueueStates(StatesGroup):
    editing = State()
from config import ADMIN_ID, is_admin, LEADS_GROUP_CHAT_ID, THREAD_ID_DRAFTS
from database import db
from agents.creative_agent import creative_agent

logger = logging.getLogger(__name__)
router = Router()

GREETING_TEXT = (
    "🏢 <b>Вас приветствует компания ТЕРИОН!</b>\n\n"
    "Я — Антон, ваш ИИ-помощник по перепланировкам.\n\n"
    "Нажимая кнопку ниже, вы даёте согласие на обработку "
    "персональных данных, получение уведомлений и информационную переписку.\n\n"
    "📞 Все консультации носят информационный характер, "
    "финальное решение подтверждает эксперт ТЕРИОН."
)


def _get_start_arg(text: str) -> str | None:
    """Параметр из /start (например: /start quiz -> quiz)."""
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

    # Брошенный квиз: если пользователь нажал /start на полпути — сохраняем тёплый лид
    current_state = await state.get_state()
    if current_state and "Quiz" in str(current_state):
        try:
            from handlers.quiz import _save_warm_lead
            await _save_warm_lead(state, user_id, message.bot)
        except Exception as _e:
            logger.debug("Сохранение тёплого лида: %s", _e)

    await state.clear()
    
    # Ссылка из канала/поста: t.me/terion_bot?start=quiz → сразу начинаем квиз (Бриф)
    if start_arg == "quiz":
        await state.set_state(QuizStates.consent_pdp)
        from handlers.quiz import get_consent_keyboard
        await message.answer(
            "📋 <b>Начинаем квиз (Бриф)</b>\n\n"
            "Перед началом необходимо ваше согласие:\n"
            "• обработка персональных данных;\n"
            "• получение уведомлений и информационная переписка.\n\n"
            "После согласия мы запросим контакт и зададим вопросы по объекту.",
            reply_markup=get_consent_keyboard(),
            parse_mode="HTML"
        )
        return

    # Активация Продавца: если пользователь — лид из шпиона (ещё не контачили), начинаем диалог первыми
    if not is_admin(user_id):
        lead = await db.get_spy_lead_uncontacted_by_author(str(user_id))
        if lead:
            await db.mark_spy_lead_contacted(lead["id"])
            source = (lead.get("source_name") or "чате").replace("<", "").replace(">", "")
            pain = (lead.get("text") or "").strip().replace("\n", " ")[:150]
            if len(lead.get("text") or "") > 150:
                pain += "…"
            await message.answer(
                "🏢 <b>Вас приветствует компания ТЕРИОН!</b>\n\n"
                f"Мы заметили ваш вопрос в <b>{source}</b> про перепланировку. "
                "Готовы подсказать по согласованию и документам — бесплатно ответим на первые вопросы.\n\n"
                "Напишите, что именно хотите сделать с объектом (квартира/дом), и мы подскажем с чего начать.",
                parse_mode="HTML"
            )
            return
    
    if is_admin(user_id):
        await message.answer(
            "🎯 <b>Главное меню</b>\n\n"
            "🕵️‍♂️ <b>Темы от Шпиона</b> — горячие идеи из чатов → сохранить в контент-план\n"
            "💰 <b>Инвест-калькулятор</b> — покажите клиенту прирост стоимости после перепланировки\n"
            "📝 <b>Записаться на консультацию</b> — запустить квиз\n\n"
            "<i>Для публикаций → контент-бот</i>",
            reply_markup=get_admin_menu()
        )
    else:
        await message.answer(
            GREETING_TEXT,
            reply_markup=get_main_menu(user_id)
        )


@router.message(F.text == "💰 Инвест-калькулятор")
async def invest_calc_start_handler(message: Message, state: FSMContext):
    """Инвест-калькулятор: оценка прироста стоимости после перепланировки."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await message.answer(
        "💰 <b>Инвест-калькулятор</b>\n\n"
        "Покажите клиенту, как вырастет стоимость квартиры после узаконенной перепланировки.\n\n"
        "По данным рынка: прирост составляет <b>+12–18%</b> от текущей стоимости.\n\n"
        "Нажмите кнопку, чтобы запустить расчёт:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Рассчитать прирост стоимости", callback_data="mode:invest")]
        ]),
        parse_mode="HTML"
    )


@router.callback_query(F.data.in_(["back_to_menu", "content_back"]))
async def content_back_handler(callback: CallbackQuery, state: FSMContext):
    """Назад из меню контента — в главное меню админа"""
    await state.clear()
    if is_admin(callback.from_user.id):
        await callback.message.edit_text(
            "🎯 <b>Главное меню</b>\n\n"
            "🛠 Создать пост — Текст / Фото / ИИ-Визуал → публикация TERION, ДОМ ГРАНД, MAX\n"
            "🕵️‍♂️ Темы от Шпиона\n"
            "📅 Очередь постов\n\n"
            "Выберите кнопку ниже:"
        )
    await callback.answer()


def _normalize_display_title(s: str, max_len: int = 70) -> str:
    """Читаемый заголовок: убрать «1. 1. «...»», обрезать по длине."""
    if not s:
        return "Без темы"
    s = re.sub(r"^\d+\.\s*", "", str(s).strip())
    if s.startswith("«") and s.endswith("»"):
        s = s[1:-1].strip()
    if len(s) > max_len:
        s = s[: max_len - 2].rstrip() + "…"
    return s or "Без темы"


@router.message(F.text == "🕵️‍♂️ Темы от Шпиона")
async def spy_topics_handler(message: Message, state: FSMContext):
    """Темы от Шпиона: свежие лиды → 3 идеи через CreativeAgent → сохранить в контент-план."""
    await message.answer("🔍 <b>Шпион подтягивает лиды и готовит идеи...</b>", parse_mode="HTML")
    try:
        leads = await db.get_recent_spy_leads(limit=30)
        trends = await db.get_top_trends(since_days=7)
        topics = await creative_agent.ideas_from_spy_leads(leads, count=3, trends=trends)
        await state.update_data(scout_topics=topics)
        text = "🕵️‍♂️ <b>Темы от Шпиона</b>\n\n"
        text += "Горячие идеи из чатов. Сохраните в черновики — и доработайте в контент-боте:\n\n"
        buttons = []
        for i, topic in enumerate(topics, 1):
            title = _normalize_display_title(topic.get("title", ""))
            insight = (topic.get("insight") or "").strip()
            text += f"<b>{i}. {title}</b>\n   💡 {insight}\n\n"
            buttons.append([
                InlineKeyboardButton(text=f"📋 В черновики #{i}", callback_data=f"to_draft_{i}"),
                InlineKeyboardButton(text=f"🖼 Обложка #{i}", callback_data=f"gen_img_{i}"),
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


@router.callback_query(F.data.startswith("create_post_"))
async def create_post_from_topic_handler(callback: CallbackQuery, state: FSMContext):
    """Сохранить тему в черновики контент-плана."""
    topic_idx = int(callback.data.split("_")[-1]) - 1
    data = await state.get_data()
    topics = data.get("scout_topics", [])
    if topic_idx < 0 or topic_idx >= len(topics):
        await callback.answer("❌ Тема не найдена")
        return
    topic = topics[topic_idx]
    title = _normalize_display_title(topic.get("title", ""), max_len=200)
    body = (topic.get("insight") or "").strip() or title
    post_id = await db.add_content_post(
        title=title,
        body=body,
        cta="Записаться на консультацию",
        channel="terion",
        status="draft",
    )
    await callback.answer(f"📋 Сохранено в черновики #{post_id}")
    await callback.message.answer(
        f"✅ <b>Идея сохранена в черновики</b> (пост #{post_id})\n\n"
        f"<b>Тема:</b> {title[:80]}{'…' if len(title) > 80 else ''}\n\n"
        f"Откройте контент-бот → <b>📅 Очередь постов</b>, чтобы доработать и опубликовать.",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("to_draft_"))
async def topic_to_draft_handler(callback: CallbackQuery, state: FSMContext):
    """Сохранить тему в черновики → карточка в рабочей группе (THREAD_ID_DRAFTS)."""
    topic_idx = int(callback.data.split("_")[-1]) - 1
    data = await state.get_data()
    topics = data.get("scout_topics", [])
    if topic_idx < 0 or topic_idx >= len(topics):
        await callback.answer("❌ Тема не найдена")
        return
    topic = topics[topic_idx]
    title = _normalize_display_title(topic.get("title", ""), max_len=200)
    insight = (topic.get("insight") or "").strip()
    body = insight or title
    post_id = await db.add_content_post(
        title=title,
        body=body,
        cta="Записаться на консультацию",
        channel="terion",
        status="draft",
    )
    await callback.answer(f"📋 Сохранено #{post_id}")

    # Карточка в рабочую группу → Юлия действует прямо там
    try:
        from handlers.admin import send_draft_to_group
        await send_draft_to_group(callback.bot, post_id, title, insight or title[:150])
        await callback.message.answer(
            f"✅ <b>Тема #{post_id} сохранена</b>\n\n"
            f"Карточка отправлена в рабочую группу — нажмите там «✍️ Написать пост», "
            f"и AI создаст текст с обложкой.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning("to_draft_handler: send_draft_to_group failed: %s", e)
        await callback.message.answer(
            f"✅ <b>Тема #{post_id} сохранена в черновики.</b>\n\n"
            f"<i>Уведомление в группу не отправлено: {e}</i>",
            parse_mode="HTML",
        )

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



def _format_scheduler_status() -> str:
    """Краткий статус запланированных задач APScheduler."""
    try:
        from services.scheduler_ref import get_scheduler
        sched = get_scheduler()
        if not sched:
            return ""
        lines = []
        for job in sched.get_jobs():
            next_run = getattr(job, "next_run_time", None)
            when = next_run.strftime("%H:%M %d.%m") if next_run else "—"
            label = getattr(job, "id", None) or getattr(job, "name", None) or "задача"
            lines.append(f"• {label}: след. запуск {when}")
        if lines:
            return "⏰ <b>По расписанию</b>\n" + "\n".join(lines[:5]) + "\n\n"
    except Exception:
        pass
    return ""


@router.message(F.text == "📅 Очередь постов")
async def queue_handler(message: Message, state: FSMContext):
    """Очередь постов: черновики из БД + статус задач APScheduler, с кнопками действий."""
    await message.answer("📅 <b>Очередь постов</b>\n\nЗагрузка...", parse_mode="HTML")
    try:
        posts = await db.get_draft_posts()
        text = "📅 <b>Очередь постов</b>\n\n"
        text += _format_scheduler_status()
        if not posts:
            text += "📭 Черновиков пока нет. Добавьте пост через <b>🛠 Создать пост</b> или из <b>🕵️‍♂️ Темы от Шпиона</b> (кнопка «В черновики»)."
            await message.answer(text, parse_mode="HTML")
            return
        text += "📋 <b>Черновики</b> (можно опубликовать или отредактировать):\n\n"
        buttons = []
        for post in posts[-10:]:
            pid = post.get("id", "?")
            status = "⏳" if post.get("status") == "draft" else "📤"
            topic = _normalize_display_title(post.get("title") or post.get("body", "Без темы")[:200], max_len=55)
            text += f"{status} #{pid} — {topic}\n"
            buttons.append([
                InlineKeyboardButton(text=f"📤 Опубликовать #{pid}", callback_data=f"queue_pub_{pid}"),
                InlineKeyboardButton(text=f"✏️ Редактировать #{pid}", callback_data=f"queue_edit_{pid}"),
            ])
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        logger.exception("queue_handler")
        await message.answer(f"❌ Ошибка: {e}")


@router.callback_query(F.data.startswith("queue_pub_"))
async def queue_publish_handler(callback: CallbackQuery, state: FSMContext):
    """Опубликовать пост из очереди (черновик) во все каналы."""
    try:
        post_id = int(callback.data.replace("queue_pub_", ""))
    except ValueError:
        await callback.answer("❌ Неверный ID")
        return
    post = await db.get_content_post(post_id)
    if not post:
        await callback.answer("❌ Пост не найден")
        return
    title = (post.get("title") or "").strip()
    body = (post.get("body") or "").strip()
    text = f"📌 <b>{title}</b>\n\n{body}\n\n#перепланировка #согласование #терион" if title else body + "\n\n#перепланировка #согласование #терион"
    await callback.answer("📤 Публикую...")
    results = await publisher.publish_all(text, image_bytes=None)
    await db.mark_as_published(post_id)
    success = sum(1 for r in results.values() if r)
    await callback.message.answer(
        f"✅ Пост #{post_id} опубликован. Успешно: {success}/{len(results)} каналов.",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("queue_edit_"))
async def queue_edit_handler(callback: CallbackQuery, state: FSMContext):
    """Редактировать пост из очереди: запросить новый текст."""
    try:
        post_id = int(callback.data.replace("queue_edit_", ""))
    except ValueError:
        await callback.answer("❌ Неверный ID")
        return
    post = await db.get_content_post(post_id)
    if not post:
        await callback.answer("❌ Пост не найден")
        return
    await state.set_state(QueueStates.editing)
    await state.update_data(queue_edit_post_id=post_id)
    await callback.answer()
    await callback.message.answer(
        f"✏️ <b>Редактирование поста #{post_id}</b>\n\n"
        "Отправьте одним сообщением новый текст поста (первая строка — заголовок, остальное — тело). Или /cancel для отмены.",
        parse_mode="HTML"
    )


@router.message(QueueStates.editing, F.text)
async def queue_edit_text_handler(message: Message, state: FSMContext):
    """Принять новый текст поста и сохранить в контент-план."""
    if not is_admin(message.from_user.id):
        return
    if message.text and message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("Отмена редактирования.")
        return
    data = await state.get_data()
    post_id = data.get("queue_edit_post_id")
    if not post_id:
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст не должен быть пустым. Отправьте снова или /cancel.")
        return
    lines = text.split("\n", 1)
    title = lines[0].strip()
    body = lines[1].strip() if len(lines) > 1 else title
    await db.update_content_plan_entry(post_id, title=title, body=body)
    await state.clear()
    await message.answer(f"✅ Пост #{post_id} обновлён. Заголовок и тело сохранены. Откройте <b>📅 Очередь постов</b>, чтобы опубликовать.", parse_mode="HTML")


@router.message(lambda m: m.text and m.text.startswith("Срочно:"))
async def urgent_handler(message: Message, state: FSMContext):
    """Обработка срочных сообщений от Юлии"""
    user_id = message.from_user.id
    logger.info(f"🚀 Срочно от: {user_id}")
    
    if not is_admin(user_id):
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
