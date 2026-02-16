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
from config import LEADS_GROUP_CHAT_ID, THREAD_ID_KVARTIRY, THREAD_ID_KOMMERCIA, THREAD_ID_DOMA

logger = logging.getLogger(__name__)
router = Router()


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
