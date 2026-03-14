<<<<<<< HEAD
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
=======
"""
Квиз для сбора заявок на перепланировку (FSM).
Логика: Старт -> Greeting (кнопка контакта) -> Contact -> Город -> ... -> План.
Поддержка голосовых: транскрибация через Yandex SpeechKit, в заявку попадает текст.
Доп. фото и документы пересылаются в тот же топик при отправке заявки.
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from database import db
from config import LEADS_GROUP_CHAT_ID, THREAD_ID_KVARTIRY, THREAD_ID_KOMMERCIA, THREAD_ID_DOMA, THREAD_ID_LOGS

logger = logging.getLogger(__name__)
router = Router()
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377

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

<<<<<<< HEAD
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
        "👋 Вас приветствует компания <b>ТЕРИОН</b>!\n\n"
        "Я — Антон, ваш ИИ-помощник по согласованию перепланировок.\n\n"
        "Нажимая кнопку ниже, вы:\n"
        "✅ Даёте согласие на обработку персональных данных\n"
        "✅ Соглашаетесь на получение уведомлений и информационную переписку\n\n"
        "Консультации носят информационный характер — финальное решение "
        "подтверждает эксперт ТЕРИОН.\n\n"
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
            f"Эксперт компании <b>ТЕРИОН</b> свяжется с вами в ближайшее время.\n\n"
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
=======
def _make_text_message(original: Message, text: str):
    """Подмена сообщения с текстом (для передачи транскрибации в те же обработчики)."""
    class T:
        text = text
        from_user = original.from_user
        answer = original.answer
        bot = getattr(original, "bot", None)
    return T()

# === РАБОЧЕЕ ВРЕМЯ (МСК) ===
WORKING_HOURS_TEXT = (
    "⏰ <b>Рабочие дни:</b> пн–пт\n"
    "📅 <b>Выходные:</b> сб–вс\n"
    "🕐 <b>Время:</b> по Москве (МСК) 9:00–20:00"
)

# === FSM STATES ===
class QuizStates(StatesGroup):
    consent_pdp = State()     # Согласие на обработку ПД, уведомления, переписку
    greeting = State()        # Согласие на контакт → кнопка «Отправить контакт»
    city = State()
    object_type = State()
    floors = State()
    area = State()
    status = State()
    description = State()
    plan = State()
    extra = State()           # Доп. вопросы и документы (всё к одной заявке)

# === KEYBOARDS ===
def get_consent_keyboard():
    """Кнопка согласия на обработку ПД"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Принимаю")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_contact_keyboard():
    """Кнопка отправки контакта (после согласия с ПД)"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить контакт", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_extra_done_keyboard():
    """Готово / пропустить доп. вопросы"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Готово, отправить заявку")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_object_type_keyboard():
    """Тип объекта"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Квартира")],
            [KeyboardButton(text="🏢 Коммерция")],
            [KeyboardButton(text="🏡 Дом")],
        ],
        resize_keyboard=True
    )


def get_status_keyboard():
    """Статус перепланировки"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Планируется")],
            [KeyboardButton(text="✅ Выполнена")],
            [KeyboardButton(text="🔄 В процессе")],
        ],
        resize_keyboard=True
    )


# === СКЛОНЕНИЯ ===
def _floors_word(n: int) -> str:
    """Этаж / этажа / этажей"""
    n = int(n) if isinstance(n, (int, float)) else int(float(str(n).replace(",", ".")))
    if 11 <= n % 100 <= 19:
        return "этажей"
    if n % 10 == 1:
        return "этаж"
    if 2 <= n % 10 <= 4:
        return "этажа"
    return "этажей"


# === THREAD ID ПО ТИПУ ОБЪЕКТА ===
def get_thread_id(object_type: str) -> int:
    """Возвращает thread_id в зависимости от типа объекта"""
    if "квартира" in object_type.lower():
        return THREAD_ID_KVARTIRY
    elif "коммерц" in object_type.lower():
        return THREAD_ID_KOMMERCIA
    elif "дом" in object_type.lower():
        return THREAD_ID_DOMA
    else:
        return THREAD_ID_KVARTIRY


# === УТИЛИТА: сохранить «Тёплый» при брошенном квизе ===
async def _save_warm_lead(state: FSMContext, user_id: int, bot: Bot):
    """
    Если пользователь бросил квиз на полпути — сохраняем то, что успел заполнить,
    со статусом «Теплый». Лид уходит в топик Логи для отслеживания.
    """
    data = await state.get_data()
    if not data:
        return
    user_name = data.get("user_name") or data.get("first_name") or f"id{user_id}"
    phone = data.get("phone", "не получен")
    city = data.get("city", "—")
    filled = [k for k in ("city", "object_type", "floors", "area", "status", "description") if data.get(k)]
    if not filled:
        return  # ничего не заполнено — не сохраняем
    try:
        lead_id = await db.add_lead(
            user_id=user_id,
            name=user_name,
            phone=phone,
            city=city,
            object_type=data.get("object_type", ""),
            total_floors=data.get("floors", ""),
            area=data.get("area", ""),
            remodeling_status=data.get("status", "Квиз не завершён"),
            change_plan=data.get("description", ""),
            extra_questions="[Квиз брошен]",
        )
        # Помечаем как тёплый
        try:
            await db.update_lead_status(lead_id, "warm")
        except Exception:
            pass
        # Уведомление в топик Логи
        text = (
            f"🟡 <b>Брошен квиз — Тёплый лид</b>\n\n"
            f"👤 {user_name} | 📞 {phone}\n"
            f"📍 Город: {city}\n"
            f"Заполнено шагов: {len(filled)} / 6\n"
            f"tg://user?id={user_id}"
        )
        await bot.send_message(
            LEADS_GROUP_CHAT_ID,
            text,
            message_thread_id=THREAD_ID_LOGS,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.debug("Не удалось сохранить тёплый лид: %s", e)


# === СОГЛАСИЕ С ПД → КОНТАКТ ===
def _is_consent_text(text: str) -> bool:
    """Проверка: пользователь принял согласие (любой вариант формулировки/клиента)."""
    if not text or not text.strip():
        return False
    t = text.strip().lower()
    return (
        "принимаю" in t
        or "согласен" in t
        or "согласна" in t
        or t == "да"
        or t == "yes"
    )


@router.message(QuizStates.consent_pdp, F.text)
async def process_consent_accept(message: Message, state: FSMContext):
    """После согласия — запрос контакта. Принимаем любую форму «принимаю/согласен»."""
    if not _is_consent_text(message.text or ""):
        await message.answer(
            "Пожалуйста, нажмите кнопку <b>«✅ Принимаю»</b>, чтобы продолжить.",
            reply_markup=get_consent_keyboard(),
            parse_mode="HTML"
        )
        return
    await state.set_state(QuizStates.greeting)
    await message.answer(
        "✅ Спасибо. Теперь нужен контакт для связи.\n\n"
        "Нажмите кнопку ниже:",
        reply_markup=get_contact_keyboard(),
        parse_mode="HTML"
    )


@router.message(QuizStates.consent_pdp)
async def process_consent_fallback(message: Message, state: FSMContext):
    """Фолбэк: не текст (фото и т.д.) — просим нажать кнопку."""
    await message.answer(
        "Пожалуйста, нажмите кнопку <b>«✅ Принимаю»</b>, чтобы продолжить.",
        reply_markup=get_consent_keyboard(),
        parse_mode="HTML"
    )


# === GREETING -> CONTACT ===
@router.message(QuizStates.greeting, F.contact)
async def process_contact(message: Message, state: FSMContext):
    """Контакт получен — переходим к вопросам"""
    user_name = message.from_user.full_name or message.from_user.first_name or "Клиент"
    phone = message.contact.phone_number
    await state.update_data(user_name=user_name, phone=phone)
    await message.answer(
        f"✅ {user_name}, контакт получен.\n\n"
        "Ответьте, пожалуйста, на несколько вопросов об объекте:",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await message.answer(
        "🏙️ <b>1. В каком городе находится объект?</b>",
        parse_mode="HTML"
    )
    await state.set_state(QuizStates.city)


@router.message(QuizStates.greeting)
async def process_greeting_fallback(message: Message, state: FSMContext):
    """Ожидаем только контакт"""
    await message.answer(
        "📱 Нажмите кнопку <b>«📱 Отправить контакт»</b> ниже.",
        reply_markup=get_contact_keyboard(),
        parse_mode="HTML"
    )


# === CITY ===
@router.message(QuizStates.city)
async def process_city(message: Message, state: FSMContext):
    """Город"""
    city = message.text.strip()
    await state.update_data(city=city)
    
    await message.answer(
        f"📍 <b>Город: {city}</b>\n\n"
        "🏠 <b>2. Какой тип объекта?</b>",
        reply_markup=get_object_type_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(QuizStates.object_type)


# === OBJECT TYPE ===
@router.message(QuizStates.object_type, F.text.in_(["🏠 Квартира", "🏢 Коммерция", "🏡 Дом"]))
async def process_object_type(message: Message, state: FSMContext):
    """Тип объекта"""
    object_type = message.text
    await state.update_data(object_type=object_type)
    
    await message.answer(
        f"🏢 <b>Тип объекта: {object_type}</b>\n\n"
        "🔢 <b>3. Какая этажность дома?</b>\n\n"
        "(Напишите цифру, например: 9 или 5)",
        parse_mode="HTML"
    )
    await state.set_state(QuizStates.floors)


# === FLOORS ===
@router.message(QuizStates.floors)
async def process_floors(message: Message, state: FSMContext):
    """Этажность"""
    raw = message.text.strip().replace(",", ".")
    try:
        n = int(float(raw.split()[0]))
    except (ValueError, IndexError):
        n = 0
    floors = message.text.strip()
    await state.update_data(floors=floors)
    word = _floors_word(n)
    await message.answer(
        f"🏢 <b>Этажность: {floors} {word}</b>\n\n"
        "📐 <b>4. Какая площадь объекта?</b>\n\n"
        "(Напишите число в кв.м., например: 45 или 120)",
        parse_mode="HTML"
    )
    await state.set_state(QuizStates.area)


# === AREA ===
@router.message(QuizStates.area)
async def process_area(message: Message, state: FSMContext):
    """Площадь"""
    area = message.text.strip().replace(",", ".").split()[0]
    await state.update_data(area=area)
    
    await message.answer(
        f"📐 <b>Площадь: {area} кв.м.</b>\n\n"
        "📋 <b>5. Какой статус перепланировки?</b>",
        reply_markup=get_status_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(QuizStates.status)


# === STATUS ===
@router.message(QuizStates.status, F.text.in_(["📋 Планируется", "✅ Выполнена", "🔄 В процессе"]))
async def process_status(message: Message, state: FSMContext):
    """Статус перепланировки"""
    status = message.text.split(maxsplit=1)[1] if message.text else ""
    await state.update_data(status=status)
    
    await message.answer(
        f"📋 <b>Статус: {status}</b>\n\n"
        "📝 <b>6. Опишите планируемые/выполненные изменения:</b>\n\n"
        "(Например: объединение кухни и гостиной, снос перегородки)",
        parse_mode="HTML"
    )
    await state.set_state(QuizStates.description)


# === DESCRIPTION ===
@router.message(QuizStates.description)
async def process_description(message: Message, state: FSMContext):
    """Описание изменений"""
    description = message.text.strip()
    await state.update_data(description=description)
    
    await message.answer(
        f"📝 <b>Описание изменений сохранено</b>\n\n"
        "🏗️ <b>7. План помещения:</b>\n\n"
        "📸 <b>Загрузите фото плана</b> (схема/чертеж) "
        "или напишите «Нет плана»",
        parse_mode="HTML"
    )
    await state.set_state(QuizStates.plan)


# === ГОЛОСОВЫЕ: транскрибация (Yandex SpeechKit), в заявку попадает текст ===
async def _handle_voice_in_quiz(message: Message, state: FSMContext, bot: Bot):
    from services.voice_transcribe import transcribe_voice
    await message.answer("🎤 Обрабатываю голосовое...")
    text = await transcribe_voice(None, bot=bot, file_id=message.voice.file_id)
    if not text or not text.strip():
        await message.answer(
            "Не удалось распознать речь. Напишите, пожалуйста, ответ текстом.",
            parse_mode="HTML"
        )
        return
    msg = _make_text_message(message, text.strip())
    current = await state.get_state()
    if current and "city" in current:
        await process_city(msg, state)
    elif current and "floors" in current:
        await process_floors(msg, state)
    elif current and "area" in current:
        await process_area(msg, state)
    elif current and "description" in current:
        await process_description(msg, state)
    else:
        await message.answer("Здесь лучше написать текстом или выбрать кнопку.", parse_mode="HTML")


@router.message(QuizStates.city, F.voice)
@router.message(QuizStates.floors, F.voice)
@router.message(QuizStates.area, F.voice)
@router.message(QuizStates.description, F.voice)
async def voice_quiz_step(message: Message, state: FSMContext, bot: Bot):
    await _handle_voice_in_quiz(message, state, bot)


# === PLAN ===
@router.message(QuizStates.plan)
async def process_plan(message: Message, state: FSMContext, bot: Bot):
    """План помещения — сохраняем и переходим к доп. вопросам/документам"""
    data = await state.get_data()
    if message.photo:
        plan_photo_id = message.photo[-1].file_id
        plan_text = "План загружен"
        has_plan_photo = True
    elif message.text and message.text.strip().lower() in ["нет плана", "нет", "❌ нет плана"]:
        plan_photo_id = None
        plan_text = "Нет плана"
        has_plan_photo = False
    elif message.text:
        plan_photo_id = None
        plan_text = message.text.strip()
        has_plan_photo = False
    else:
        plan_photo_id = None
        plan_text = "Нет плана"
        has_plan_photo = False
    await state.update_data(
        plan_text=plan_text,
        plan_photo_id=plan_photo_id,
        has_plan_photo=has_plan_photo,
        extra_parts=[]
    )
    await message.answer(
        f"🏗️ <b>План:</b> {plan_text}\n\n"
        "📎 <b>Дополнительно</b> (по желанию): вы можете загрузить документы или задать вопросы — текстом или голосовым. Всё попадёт в одну заявку.\n\n"
        "Или нажмите <b>«Готово»</b>, чтобы отправить заявку.",
        reply_markup=get_extra_done_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(QuizStates.extra)


# === EXTRA: доп. вопросы и документы (одна заявка) ===
@router.message(QuizStates.extra, F.text.in_(["✅ Готово, отправить заявку", "Готово", "Отправить"]))
async def process_extra_done(message: Message, state: FSMContext, bot: Bot):
    """Отправка одной заявки с учётом доп. материалов"""
    data = await state.get_data()
    user_name = data.get("user_name", "Клиент")
    phone = data.get("phone", "Не указан")
    plan_text = data.get("plan_text", "Нет плана")
    plan_photo_id = data.get("plan_photo_id")
    has_plan_photo = data.get("has_plan_photo", False)
    extra_parts = data.get("extra_parts") or []
    object_type = data.get("object_type", "")
    thread_id = get_thread_id(object_type)
    floors = data.get("floors", "")
    try:
        n = int(float(str(floors).replace(",", ".").split()[0]))
        floors_word = _floors_word(n)
    except Exception:
        floors_word = "этажей"
    lead_text = (
        f"🔥 <b>Новая заявка!</b>\n\n"
        f"👤 <b>Клиент:</b> {user_name}\n"
        f"📞 <b>Телефон:</b> {phone}\n"
        f"📍 <b>Город:</b> {data.get('city', '—')}\n"
        f"🏠 <b>Тип объекта:</b> {data.get('object_type', '—')}\n"
        f"🔢 <b>Этажность дома:</b> {floors} {floors_word}\n"
        f"📐 <b>Площадь:</b> {data.get('area', '—')} кв.м.\n"
        f"📋 <b>Статус перепланировки:</b> {data.get('status', '—')}\n\n"
        f"📝 <b>Описание:</b>\n{data.get('description', '—')}\n\n"
        f"🏗️ <b>План:</b> {plan_text}"
    )
    # Только текстовые части в блок доп. и в БД; файлы пересылаем отдельно в топик
    extra_texts = []
    extra_files = []
    for p in extra_parts:
        if isinstance(p, dict):
            extra_files.append(p)
            extra_texts.append(f"[{p.get('type', 'файл')}: {p.get('file_name', 'файл')}]")
        else:
            extra_texts.append(str(p))
    if extra_texts:
        lead_text += "\n\n📎 <b>Доп. вопросы/документы:</b>\n" + "\n".join(extra_texts)
    try:
        if has_plan_photo and plan_photo_id:
            await bot.send_photo(
                chat_id=LEADS_GROUP_CHAT_ID,
                message_thread_id=thread_id,
                photo=plan_photo_id,
                caption=lead_text,
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                chat_id=LEADS_GROUP_CHAT_ID,
                message_thread_id=thread_id,
                text=lead_text,
                parse_mode="HTML"
            )
        # Пересылка доп. фото и документов в тот же топик
        for f in extra_files:
            try:
                if f.get("type") == "photo" and f.get("file_id"):
                    await bot.send_photo(
                        chat_id=LEADS_GROUP_CHAT_ID,
                        message_thread_id=thread_id,
                        photo=f["file_id"],
                        caption="📎 Доп. к заявке",
                        parse_mode="HTML"
                    )
                elif f.get("type") == "document" and f.get("file_id"):
                    await bot.send_document(
                        chat_id=LEADS_GROUP_CHAT_ID,
                        message_thread_id=thread_id,
                        document=f["file_id"],
                        caption="📎 Доп. к заявке" + (f" — {f.get('file_name', '')}" if f.get("file_name") else ""),
                        parse_mode="HTML"
                    )
            except Exception as file_err:
                logger.warning("Не удалось переслать файл в топик: %s", file_err)
        lead_id = await db.add_lead(
            user_id=message.from_user.id,
            name=user_name,
            phone=phone,
            city=data.get("city", ""),
            object_type=data.get("object_type", ""),
            total_floors=data.get("floors", ""),
            area=data.get("area", ""),
            remodeling_status=data.get("status", ""),
            change_plan=data.get("description", ""),
            extra_questions="\n---\n".join(extra_texts) if extra_texts else None,
        )
        await db.set_lead_thread(lead_id, thread_id)

        # Умный квиз v2: сводка -> Агент-Антон -> предварительное заключение, уведомление Юлии
        quiz_summary = (
            f"Клиент: {user_name}, телефон: {phone}. "
            f"Город: {data.get('city', '—')}. Тип объекта: {data.get('object_type', '—')}. "
            f"Этажность: {data.get('floors', '—')}. Площадь: {data.get('area', '—')} кв.м. "
            f"Статус перепланировки: {data.get('status', '—')}. "
            f"Описание: {data.get('description', '—')}. План: {plan_text}."
        )
        if extra_texts:
            quiz_summary += " Доп. вопросы/документы: " + "; ".join(extra_texts[:5])
        conclusion = ""
        try:
            from utils.yandex_ai_agents import call_anton_quiz_summary
            conclusion = await call_anton_quiz_summary(quiz_summary)
        except Exception as e:
            logger.warning("Anton quiz conclusion failed: %s", e)
        if conclusion:
            await message.answer(
                f"📋 <b>Предварительное заключение эксперта Юлии Пархоменко</b>\n\n{conclusion}",
                parse_mode="HTML",
            )
        try:
            julia_notice = "📌 Лид из чата ЖК прошел квиз. Вероятность сделки: Высокая."
            if conclusion:
                julia_notice += f"\n\n{conclusion[:500]}"
            await bot.send_message(
                chat_id=LEADS_GROUP_CHAT_ID,
                message_thread_id=thread_id,
                text=julia_notice,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning("Julia quiz notification failed: %s", e)
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки заявки. Попробуйте ещё раз или напишите в поддержку.", parse_mode="HTML")
        return
    await message.answer(
        f"✅ <b>{user_name}</b>, заявка отправлена!\n\n"
        f"📤 Эксперт ТЕРИОН получил всю информацию и свяжется с вами.\n\n"
        f"{WORKING_HOURS_TEXT}\n\n"
        f"❓ Если появятся вопросы — можете написать в этот чат.",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML"
    )
    await state.clear()


@router.message(QuizStates.extra, F.voice)
async def process_extra_voice(message: Message, state: FSMContext, bot: Bot):
    """Доп. вопрос голосом — транскрибация и добавление к заявке"""
    from services.voice_transcribe import transcribe_voice
    await message.answer("🎤 Обрабатываю голосовое...")
    text = await transcribe_voice(None, bot=bot, file_id=message.voice.file_id)
    if text and text.strip():
        data = await state.get_data()
        parts = data.get("extra_parts") or []
        parts.append(f"[голос] {text.strip()}")
        await state.update_data(extra_parts=parts)
        await message.answer("✅ Принято. Можете добавить ещё или нажмите «Готово».", reply_markup=get_extra_done_keyboard(), parse_mode="HTML")
    else:
        await message.answer("Не удалось распознать. Напишите текстом или нажмите «Готово».", reply_markup=get_extra_done_keyboard(), parse_mode="HTML")


@router.message(QuizStates.extra, F.text)
async def process_extra_text(message: Message, state: FSMContext):
    """Доп. вопрос текстом"""
    text = message.text.strip()
    if not text:
        return
    data = await state.get_data()
    parts = data.get("extra_parts") or []
    parts.append(text)
    await state.update_data(extra_parts=parts)
    await message.answer("✅ Принято. Ещё что-то? Или нажмите «Готово».", reply_markup=get_extra_done_keyboard(), parse_mode="HTML")


@router.message(QuizStates.extra, F.photo)
async def process_extra_photo(message: Message, state: FSMContext):
    """Доп. фото — сохраняем file_id, при «Готово» пересылаем в топик"""
    file_id = message.photo[-1].file_id
    data = await state.get_data()
    parts = data.get("extra_parts") or []
    parts.append({"type": "photo", "file_id": file_id, "file_name": "фото"})
    await state.update_data(extra_parts=parts)
    await message.answer("✅ Фото принято. Можете добавить ещё или нажмите «Готово».", reply_markup=get_extra_done_keyboard(), parse_mode="HTML")


@router.message(QuizStates.extra, F.document)
async def process_extra_document(message: Message, state: FSMContext):
    """Доп. документ — сохраняем file_id, при «Готово» пересылаем в топик"""
    doc = message.document
    file_id = doc.file_id
    name = doc.file_name or "документ"
    data = await state.get_data()
    parts = data.get("extra_parts") or []
    parts.append({"type": "document", "file_id": file_id, "file_name": name})
    await state.update_data(extra_parts=parts)
    await message.answer("✅ Документ принят. Можете добавить ещё или нажмите «Готово».", reply_markup=get_extra_done_keyboard(), parse_mode="HTML")
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
