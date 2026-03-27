from aiogram import Router, F, Dispatcher, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from config import LEADS_GROUP_CHAT_ID, THREAD_ID_HOT_LEADS, THREAD_ID_QUIZ_LEADS
from database.db import db
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)
quiz_router = Router()

# Рабочее время по МСК (UTC+3)
MSK = timezone(timedelta(hours=3))
WORK_HOUR_START = 9
WORK_HOUR_END = 20
WORK_DAYS = (0, 1, 2, 3, 4)  # Пн–Пт

def _is_work_time() -> bool:
    now = datetime.now(MSK)
    return now.weekday() in WORK_DAYS and WORK_HOUR_START <= now.hour < WORK_HOUR_END

def _next_work_time_str() -> str:
    now = datetime.now(MSK)
    if now.weekday() in WORK_DAYS and now.hour < WORK_HOUR_START:
        return f"сегодня с {WORK_HOUR_START}:00 МСК"
    if now.weekday() == 4 and now.hour >= WORK_HOUR_END:
        return f"в понедельник с {WORK_HOUR_START}:00 МСК"
    if now.weekday() in (5, 6):
        return f"в понедельник с {WORK_HOUR_START}:00 МСК"
    return f"завтра с {WORK_HOUR_START}:00 МСК"

class QuizOrder(StatesGroup):
    consent = State()
    city = State()
    object_type = State()
    house_material = State()
    floor_info = State()
    area = State()
    gas_info = State()
    remodeling_status = State()
    description = State()
    plan = State()

@quiz_router.callback_query(F.data == "mode:quiz")
async def start_quiz_callback(callback: CallbackQuery, state: FSMContext):
    """Точка входа в квиз — нажатие кнопки «Начать квиз» в главном меню."""
    await state.clear()

    text = (
        "👋 Вас приветствует компания <b>ГЕОРИС</b>!\n\n"
        "Я — Антон, ваш ИИ-помощник по согласованию перепланировок.\n\n"
        "Нажимая кнопку ниже, вы:\n"
        "✅ Даёте согласие на обработку персональных данных\n"
        "✅ Соглашаетесь на получение уведомлений и информационную переписку\n\n"
        "Консультации носят информационный характер — финальное решение "
        "подтверждает эксперт ГЕОРИС.\n\n"
        "<i>Нажмите кнопку, чтобы поделиться номером и начать опрос:</i>"
    )

    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером и согласиться", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

    await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(QuizOrder.consent)
    await callback.answer()

@quiz_router.message(QuizOrder.consent, F.contact)
async def process_consent(message: Message, state: FSMContext):
    """Клиент поделился контактом — сохраняем, переходим к вопросам."""
    contact   = message.contact
    user_name = contact.first_name or message.from_user.first_name or "Клиент"
    phone     = contact.phone_number

    # Создаём или обновляем пользователя в БД
    try:
        await db.get_or_create_user(
            user_id    = message.from_user.id,
            username   = message.from_user.username,
            first_name = message.from_user.first_name,
            last_name  = message.from_user.last_name,
        )
        # Сохраняем телефон через execute (безопасно, без прямого db.conn)
        await db.execute(
            "UPDATE users SET phone = ? WHERE user_id = ?",
            (phone, message.from_user.id),
        )
    except Exception as e:
        logger.warning("Не удалось сохранить телефон в БД: %s", e)

    await state.update_data(
        phone    = phone,
        name     = user_name,
        username = message.from_user.username or "",
        user_id  = message.from_user.id,
    )

    await message.answer(
        f"{user_name}, приятно познакомиться! 🤝\n\n"
        f"Для предварительного анализа вашего объекта задам <b>7 коротких вопросов</b>.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )
    await message.answer("1️⃣ В каком городе находится объект?")
    await state.set_state(QuizOrder.city)

@quiz_router.message(QuizOrder.consent, ~F.contact)
async def consent_wrong_input(message: Message):
    """Клиент написал текст вместо того чтобы нажать кнопку контакта."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером и согласиться", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await message.answer(
        "Пожалуйста, нажмите кнопку <b>«Поделиться номером»</b> ниже — "
        "это необходимо для того чтобы эксперт мог с вами связаться.",
        reply_markup=keyboard,
        parse_mode="HTML",
    )

@quiz_router.message(QuizOrder.city)
async def process_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Квартира"),          KeyboardButton(text="Апартаменты")],
            [KeyboardButton(text="Нежилое помещение"), KeyboardButton(text="Частный дом")],
        ],
        resize_keyboard=True,
    )
    await message.answer("2️⃣ Выберите тип объекта:", reply_markup=keyboard)
    await state.set_state(QuizOrder.object_type)

@quiz_router.message(QuizOrder.object_type)
async def process_object_type(message: Message, state: FSMContext):
    await state.update_data(object_type=message.text)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Монолит"),   KeyboardButton(text="Панельный")],
            [KeyboardButton(text="Кирпичный"), KeyboardButton(text="Не знаю")],
        ],
        resize_keyboard=True,
    )
    await message.answer("3️⃣ Тип дома:", reply_markup=keyboard)
    await state.set_state(QuizOrder.house_material)

@quiz_router.message(QuizOrder.house_material)
async def process_house_material(message: Message, state: FSMContext):
    await state.update_data(house_material=message.text)

    await message.answer(
        "4️⃣ Укажите этаж и общую этажность дома\n"
        "<i>Например: 5/17</i>",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )
    await state.set_state(QuizOrder.floor_info)

@quiz_router.message(QuizOrder.floor_info)
async def process_floor(message: Message, state: FSMContext):
    await state.update_data(floor_info=message.text)

    await message.answer(
        "5️⃣ Какая общая площадь помещения?\n"
        "<i>Укажите в кв.м, например: 54</i>",
        parse_mode="HTML",
    )
    await state.set_state(QuizOrder.area)

@quiz_router.message(QuizOrder.area)
async def process_area(message: Message, state: FSMContext):
    await state.update_data(area=message.text)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⚡ Электрическая плита")],
            [KeyboardButton(text="🔥 Газовая плита")],
        ],
        resize_keyboard=True,
    )
    await message.answer("6️⃣ Какая плита установлена на кухне?", reply_markup=keyboard)
    await state.set_state(QuizOrder.gas_info)

@quiz_router.message(QuizOrder.gas_info)
async def process_gas(message: Message, state: FSMContext):
    await state.update_data(gas_info=message.text)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔜 Планируется"),   KeyboardButton(text="✅ Уже сделана")],
            [KeyboardButton(text="⚙️ В процессе")],
        ],
        resize_keyboard=True,
    )
    await message.answer("7️⃣ Статус перепланировки:", reply_markup=keyboard)
    await state.set_state(QuizOrder.remodeling_status)

@quiz_router.message(QuizOrder.remodeling_status)
async def process_status(message: Message, state: FSMContext):
    await state.update_data(remodeling_status=message.text)

    await message.answer(
        "8️⃣ Кратко опишите планируемые или выполненные изменения:\n"
        "<i>Например: снос стены между кухней и гостиной, расширение санузла, перенос кухни</i>",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
    )
    await state.set_state(QuizOrder.description)

@quiz_router.message(QuizOrder.description)
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)

    await message.answer(
        "📎 Прикрепите план помещения — это поможет эксперту быстрее оценить ситуацию.\n\n"
        "Можно отправить:\n"
        "• фотографию плана\n"
        "• PDF-файл\n"
        "• написать <b>«нет плана»</b> если плана пока нет",
        parse_mode="HTML",
    )
    await state.set_state(QuizOrder.plan)

@quiz_router.message(QuizOrder.plan)
async def process_plan(message: Message, state: FSMContext, bot: Bot):
    """Финальный шаг: принимаем план (или его отсутствие), формируем заявку, отправляем в группу."""
    data      = await state.get_data()
    user_name = data.get("name", "Клиент")
    username  = data.get("username", "")
    user_id   = data.get("user_id", message.from_user.id)

    # Определяем что прислал клиент
    if message.photo:
        plan_info    = "📷 Фото плана"
        has_file     = True
        file_id      = message.photo[-1].file_id
        is_photo     = True
    elif message.document:
        plan_info    = f"📄 Документ: {message.document.file_name or 'файл'}"
        has_file     = True
        file_id      = message.document.file_id
        is_photo     = False
    elif message.text and message.text.strip().lower() in ("нет плана", "нет", "no"):
        plan_info    = "❌ Плана нет"
        has_file     = False
        file_id      = None
        is_photo     = False
    else:
        # Клиент написал что-то другое — сохраняем как текст
        plan_info    = f"📝 Текст: {(message.text or '')[:100]}"
        has_file     = False
        file_id      = None
        is_photo     = False

    await state.update_data(plan=plan_info)

    # Ссылка на профиль клиента
    tg_link = f"@{username}" if username else f"tg://user?id={user_id}"

    # ── Карточка заявки для рабочей группы ───────────────────────────────────
    report = (
        f"🎯 <b>НОВАЯ ЗАЯВКА (Квиз)</b>\n\n"
        f"👤 <b>Имя:</b> {user_name}\n"
        f"📞 <b>Телефон:</b> {data.get('phone', '—')}\n"
        f"✉️ <b>Telegram:</b> {tg_link}\n\n"
        f"📍 <b>Город:</b> {data.get('city', '—')}\n"
        f"🏢 <b>Объект:</b> {data.get('object_type', '—')}\n"
        f"🏗 <b>Тип дома:</b> {data.get('house_material', '—')}\n"
        f"🔢 <b>Этаж:</b> {data.get('floor_info', '—')}\n"
        f"📐 <b>Площадь:</b> {data.get('area', '—')} кв.м\n"
        f"🔥 <b>Плита:</b> {data.get('gas_info', '—')}\n"
        f"🛠 <b>Статус:</b> {data.get('remodeling_status', '—')}\n"
        f"📝 <b>Описание:</b> {data.get('description', '—')}\n"
        f"🗺 <b>План:</b> {plan_info}\n"
    )

    # Inline-кнопки для оператора
    now_str = datetime.now(MSK).strftime("%d.%m %H:%M")
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Взять в работу",  callback_data=f"quiz_take:{user_id}:{user_name[:20]}"),
            InlineKeyboardButton(text="📞 Перезвонить",     callback_data=f"quiz_call:{user_id}:{user_name[:20]}"),
        ],
        [
            InlineKeyboardButton(text="❌ Не наш клиент",   callback_data=f"quiz_skip:{user_id}"),
        ],
    ])

    # Отправляем карточку в рабочую группу
    try:
        thread_id = THREAD_ID_QUIZ_LEADS or THREAD_ID_HOT_LEADS
        await bot.send_message(
            chat_id            = LEADS_GROUP_CHAT_ID,
            text               = report,
            parse_mode         = "HTML",
            message_thread_id  = thread_id,
            reply_markup       = keyboard,
        )
        # Пересылаем план если был
        if has_file and file_id:
            caption = f"📎 План от {user_name} ({tg_link})"
            if is_photo:
                await bot.send_photo(
                    LEADS_GROUP_CHAT_ID, file_id,
                    caption=caption, message_thread_id=thread_id,
                )
            else:
                await bot.send_document(
                    LEADS_GROUP_CHAT_ID, file_id,
                    caption=caption, message_thread_id=thread_id,
                )
    except Exception as e:
        logger.error("Ошибка отправки заявки в группу: %s", e)

    # Сохраняем лид в БД
    try:
        await db.execute(
            """INSERT OR IGNORE INTO leads
               (source_id, text, author_id, author_name, url, platform, status, published_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "quiz",
                data.get("description", ""),
                str(user_id),
                user_name,
                tg_link,
                "telegram_quiz",
                "new",
                datetime.now(MSK).isoformat(),
            ),
        )
    except Exception as e:
        logger.warning("Не удалось сохранить лид в БД: %s", e)

    await state.clear()

    # ── Финальное сообщение клиенту — зависит от времени суток ───────────────
    if _is_work_time():
        final_text = (
            f"✅ {user_name}, спасибо! Заявка принята.\n\n"
            f"Эксперт компании <b>ГЕОРИС</b> свяжется с вами в ближайшее время.\n\n"
            f"Если хотите, можете прислать дополнительные фото или документы — "
            f"мы учтём их при подготовке консультации."
        )
    else:
        next_time = _next_work_time_str()
        final_text = (
            f"✅ {user_name}, спасибо! Заявка принята.\n\n"
            f"Сейчас нерабочее время. Наши специалисты работают:\n"
            f"🕘 Пн–Пт с {WORK_HOUR_START}:00 до {WORK_HOUR_END}:00 по МСК\n\n"
            f"Эксперт свяжется с вами <b>{next_time}</b>.\n\n"
            f"Если хотите, можете прислать дополнительные фото или документы прямо сейчас — "
            f"мы изучим их перед звонком."
        )

    await message.answer(final_text, reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")

@quiz_router.callback_query(F.data.startswith("quiz_take:"))
async def quiz_take(callback: CallbackQuery):
    parts     = callback.data.split(":", 2)
    client_name = parts[2].replace("_", " ") if len(parts) > 2 else "клиент"
    who       = callback.from_user.first_name or "Оператор"
    now_str   = datetime.now(MSK).strftime("%d.%m %H:%M")

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.edit_text(
        callback.message.text + f"\n\n✅ <b>Взят в работу</b> — {who} · {now_str}",
        parse_mode="HTML",
    )
    await callback.answer(f"✅ Взяли {client_name} в работу!", show_alert=True)


@quiz_router.callback_query(F.data.startswith("quiz_call:"))
async def quiz_call(callback: CallbackQuery):
    parts       = callback.data.split(":", 2)
    client_name = parts[2].replace("_", " ") if len(parts) > 2 else "клиент"
    who         = callback.from_user.first_name or "Оператор"
    now_str     = datetime.now(MSK).strftime("%d.%m %H:%M")

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.edit_text(
        callback.message.text + f"\n\n📞 <b>Запланирован звонок</b> — {who} · {now_str}",
        parse_mode="HTML",
    )
    await callback.answer(f"📞 Перезвоните {client_name}!", show_alert=True)


@quiz_router.callback_query(F.data.startswith("quiz_skip:"))
async def quiz_skip(callback: CallbackQuery):
    who     = callback.from_user.first_name or "Оператор"
    now_str = datetime.now(MSK).strftime("%d.%m %H:%M")

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.edit_text(
        callback.message.text + f"\n\n❌ <b>Не наш клиент</b> — {who} · {now_str}",
        parse_mode="HTML",
    )
    await callback.answer("Лид архивирован.")


def register_handlers(dp: Dispatcher):
    dp.include_router(quiz_router)


# Алиас для совместимости
QuizStates = QuizOrder
