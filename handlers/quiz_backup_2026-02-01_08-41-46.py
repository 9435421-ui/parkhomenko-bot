from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from config import ADMIN_GROUP_ID
from database.db import db
import json
import re

router = Router()

def validate_phone(phone: str) -> bool:
    """Простая валидация номера телефона"""
    clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
    return bool(re.match(r'^(\+7|8|7)\d{10}$', clean_phone))


@router.callback_query(F.data == "mode:quiz")
async def start_quiz_callback(callback: CallbackQuery, state: FSMContext):
    """Запуск квиза из меню"""
    await state.set_state(QuizOrder.role)
    await callback.message.answer("📋 Кто вы? (Собственник/Дизайнер/Застройщик/Инвестор/Другое)")
    await callback.answer()


class QuizOrder(StatesGroup):
    role = State()
    city = State()
    obj_type = State()
    area = State()
    status = State()
    complexity = State()
    goal = State()
    bti_doc = State()
    urgency = State()
    phone = State()


def get_progress(step: int, total: int = 10) -> str:
    return f"📍 Шаг {step} из {total}\n\n"

def handle_quiz_start():
    """Placeholder for automation script"""
    #STAGE_LOGIC
    pass


@router.message(QuizOrder.role)
async def ask_role(message: Message, state: FSMContext):
    await state.update_data(role=message.text)
    await state.set_state(QuizOrder.city)
    name = message.from_user.first_name or ""
    await message.answer(f"{get_progress(2)}{name}, из какого вы города?", reply_markup=ReplyKeyboardRemove())


@router.message(QuizOrder.city)
async def ask_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(QuizOrder.obj_type)

    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 Жилое"), KeyboardButton(text="🏢 Нежилое")]],
        resize_keyboard=True
    )
    await message.answer(f"{get_progress(3)}Какой тип объекта?", reply_markup=markup)


@router.message(QuizOrder.obj_type)
async def ask_obj_type(message: Message, state: FSMContext):
    await state.update_data(obj_type=message.text)
    await state.set_state(QuizOrder.area)
    await message.answer(f"{get_progress(4)}Укажите примерный метраж помещения (кв. м):", reply_markup=ReplyKeyboardRemove())


@router.message(QuizOrder.area)
async def ask_area(message: Message, state: FSMContext):
    await state.update_data(area=message.text)
    await state.set_state(QuizOrder.status)

    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📋 Планируется"), KeyboardButton(text="✅ Уже выполнена")]],
        resize_keyboard=True
    )
    await message.answer(f"{get_progress(5)}На какой стадии перепланировка?", reply_markup=markup)


@router.message(QuizOrder.status)
async def ask_status(message: Message, state: FSMContext):
    await state.update_data(status=message.text)
    await state.set_state(QuizOrder.complexity)

    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧱 Стены"), KeyboardButton(text="🚿 Мокрые зоны")],
            [KeyboardButton(text="❌ Нет")]
        ],
        resize_keyboard=True
    )
    await message.answer(f"{get_progress(6)}Есть ли сложные зоны (затрагивание несущих стен, перенос санузлов)?", reply_markup=markup)


@router.message(QuizOrder.complexity)
async def ask_complexity(message: Message, state: FSMContext):
    await state.update_data(complexity=message.text)
    await state.set_state(QuizOrder.goal)

    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="💰 Инвест"), KeyboardButton(text="🏠 Для жизни")]],
        resize_keyboard=True
    )
    await message.answer(f"{get_progress(7)}Какова цель перепланировки?", reply_markup=markup)


@router.message(QuizOrder.goal)
async def ask_goal(message: Message, state: FSMContext):
    await state.update_data(goal=message.text)
    await state.set_state(QuizOrder.bti_doc)

    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Есть файл/фото")],
            [KeyboardButton(text="📄 Частично")],
            [KeyboardButton(text="❌ Нет")]
        ],
        resize_keyboard=True
    )
    await message.answer(
        f"{get_progress(8)}Есть ли документы БТИ на руках?\n\n"
        "Вы можете прикрепить фото или PDF прямо сейчас или просто ответить текстом.",
        reply_markup=markup
    )


@router.message(QuizOrder.bti_doc)
async def ask_bti(message: Message, state: FSMContext):
    # Обработка файлов и фото
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
        await state.update_data(bti_doc="Загружено фото", bti_file_id=file_id)
    elif message.document:
        file_id = message.document.file_id
        await state.update_data(bti_doc=f"Загружен документ: {message.document.file_name}", bti_file_id=file_id)
    else:
        await state.update_data(bti_doc=message.text)

    await state.set_state(QuizOrder.urgency)

    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔥 Срочно"), KeyboardButton(text="⏳ Можно подождать")]],
        resize_keyboard=True
    )
    await message.answer(f"{get_progress(9)}Насколько срочно нужно решить вопрос?", reply_markup=markup)


@router.message(QuizOrder.urgency)
async def ask_urgency(message: Message, state: FSMContext):
    await state.update_data(urgency=message.text)
    await state.set_state(QuizOrder.phone)

    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        f"{get_progress(10)}Оставьте, пожалуйста, ваш номер телефона для связи.\n\n"
        "Вы можете нажать кнопку «Поделиться контактом» ниже или ввести номер вручную.",
        reply_markup=markup
    )


@router.message(QuizOrder.phone)
async def finish_quiz(message: Message, state: FSMContext):
    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = message.text
        if not validate_phone(phone):
            await message.answer("Пожалуйста, введите корректный номер телефона (например, +79991234567)")
            return

    await state.update_data(phone=phone)
    data = await state.get_data()

    # Формируем расширенную сводку для админа
    file_info = f"\n📎 <b>Файл:</b> Да (ID: {data.get('bti_file_id')})" if data.get('bti_file_id') else "\n📎 <b>Файл:</b> Нет"

    summary = (
        f"🚀 <b>НОВАЯ ЗАЯВКА (КВИЗ {data.get('status')})</b>\n\n"
        f"👤 <b>Клиент:</b> {message.from_user.full_name}\n"
        f"🆔 <b>TG ID:</b> <code>{message.from_user.id}</code>\n"
        f"📱 <b>Телефон:</b> {data.get('phone')}\n"
        f"🏙 <b>Город:</b> {data.get('city')}\n"
        f"📐 <b>Метраж:</b> {data.get('area')} кв.м\n"
        f"🏢 <b>Тип:</b> {data.get('obj_type')}\n"
        f"🧱 <b>Сложность:</b> {data.get('complexity')}\n"
        f"🎯 <b>Цель:</b> {data.get('goal')}\n"
        f"📄 <b>БТИ:</b> {data.get('bti_doc')}{file_info}\n"
        f"🔥 <b>Срочность:</b> {data.get('urgency')}\n"
        f"🔗 <b>Источник:</b> <code>{data.get('_payload') or 'direct'}</code>"
    )

    # Отправка в админ-группу
    try:
        if data.get('bti_file_id'):
            await message.bot.send_document(
                chat_id=ADMIN_GROUP_ID,
                document=data.get('bti_file_id'),
                caption=summary,
                parse_mode="HTML"
            )
        else:
            await message.bot.send_message(chat_id=ADMIN_GROUP_ID, text=summary, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка отправки уведомления админу: {e}")
        await message.bot.send_message(chat_id=ADMIN_GROUP_ID, text=summary, parse_mode="HTML")

    # Ветвление финального контента для пользователя
    status = data.get('status', '').lower()
    name = message.from_user.first_name or "клиент"

    if "уже выполнена" in status:
        final_text = (
            f"✅ <b>Спасибо, {name}! Ваша заявка принята.</b>\n\n"
            "Так как перепланировка уже выполнена, мы подготовим для вас план легализации:\n"
            "1️⃣ Проверим допустимость выполненных работ.\n"
            "2️⃣ Оценим риски штрафов и предписаний.\n"
            "3️⃣ Подскажем, как узаконить всё без судов.\n\n"
            "Наш эксперт свяжется с вами в ближайшее рабочее время."
        )
    else:
        final_text = (
            f"✅ <b>Спасибо, {name}! Заявка успешно оформлена.</b>\n\n"
            "Для вашей будущей перепланировки мы подготовим:\n"
            "1️⃣ Расчет стоимости проектирования и согласования.\n"
            "2️⃣ Пошаговый алгоритм действий именно для вашего случая.\n"
            "3️⃣ Список необходимых документов БТИ и ЕГРН.\n\n"
            "Эксперт позвонит вам для уточнения деталей."
        )

    # Кнопка для записи на консультацию
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Выбрать время консультации", url="https://t.me/torion_expert")]
        ]
    )

    await message.answer(final_text, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    await message.answer("Вы также можете написать нашему эксперту напрямую в Telegram:", reply_markup=markup)

    # Сохранение в единую базу лидов
    try:
        await db.add_unified_lead(
            user_id=message.from_user.id,
            source_bot="qualification",
            phone=data.get('phone'),
            name=message.from_user.full_name,
            username=message.from_user.username,
            lead_type="quiz",
            details=json.dumps(data, ensure_ascii=False)
        )
    except Exception as e:
        print(f"Ошибка сохранения лида: {e}")

    await state.clear()
