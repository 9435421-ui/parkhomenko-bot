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
    status = State()
    complexity = State()
    goal = State()
    bti_doc = State()
    urgency = State()
    phone = State()


@router.message(QuizOrder.role)
async def ask_role(message: Message, state: FSMContext):
    await state.update_data(role=message.text)
    await state.set_state(QuizOrder.city)
    await message.answer("Из какого вы города?", reply_markup=ReplyKeyboardRemove())


@router.message(QuizOrder.city)
async def ask_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(QuizOrder.obj_type)

    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 Жилое"), KeyboardButton(text="🏢 Нежилое")]],
        resize_keyboard=True
    )
    await message.answer("Какой тип объекта?", reply_markup=markup)


@router.message(QuizOrder.obj_type)
async def ask_obj_type(message: Message, state: FSMContext):
    await state.update_data(obj_type=message.text)
    await state.set_state(QuizOrder.status)

    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📋 Планируется"), KeyboardButton(text="✅ Уже выполнена")]],
        resize_keyboard=True
    )
    await message.answer("На какой стадии перепланировка?", reply_markup=markup)


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
    await message.answer("Есть ли сложные зоны (затрагивание несущих стен, перенос санузлов)?", reply_markup=markup)


@router.message(QuizOrder.complexity)
async def ask_complexity(message: Message, state: FSMContext):
    await state.update_data(complexity=message.text)
    await state.set_state(QuizOrder.goal)

    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="💰 Инвест"), KeyboardButton(text="🏠 Для жизни")]],
        resize_keyboard=True
    )
    await message.answer("Какова цель перепланировки?", reply_markup=markup)


@router.message(QuizOrder.goal)
async def ask_goal(message: Message, state: FSMContext):
    await state.update_data(goal=message.text)
    await state.set_state(QuizOrder.bti_doc)

    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да"), KeyboardButton(text="📄 Частично")],
            [KeyboardButton(text="❌ Нет")]
        ],
        resize_keyboard=True
    )
    await message.answer("Есть ли документы БТИ на руках?", reply_markup=markup)


@router.message(QuizOrder.bti_doc)
async def ask_bti(message: Message, state: FSMContext):
    await state.update_data(bti_doc=message.text)
    await state.set_state(QuizOrder.urgency)

    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔥 Срочно"), KeyboardButton(text="⏳ Можно подождать")]],
        resize_keyboard=True
    )
    await message.answer("Насколько срочно нужно решить вопрос?", reply_markup=markup)


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
        "Оставьте, пожалуйста, ваш номер телефона для связи.\n"
        "Вы можете нажать кнопку ниже или ввести номер вручную.",
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

    summary = (
        f"📋 <b>Новая заявка (Квиз)</b>\n\n"
        f"👤 Пользователь: @{message.from_user.username or 'без username'} ({message.from_user.id})\n"
        f"📞 Телефон: {data.get('phone')}\n"
        f"🏙 Город: {data.get('city')}\n"
        f"🏗 Тип: {data.get('obj_type')}\n"
        f"📅 Стадия: {data.get('status')}\n"
        f"🧱 Сложность: {data.get('complexity')}\n"
        f"🎯 Цель: {data.get('goal')}\n"
        f"📄 БТИ: {data.get('bti_doc')}\n"
        f"⏱ Срочность: {data.get('urgency')}\n"
        f"🔗 Источник: {data.get('_payload') or 'не определен'}"
    )

    await message.bot.send_message(chat_id=ADMIN_GROUP_ID, text=summary, parse_mode="HTML")

    # Ветвление финального контента
    status = data.get('status', '').lower()

    if "уже выполнена" in status:
        final_text = (
            "⚠️ <b>Важная информация по выполненной перепланировке:</b>\n\n"
            "Так как ремонт уже сделан, процедура легализации отличается от стандартной.\n"
            "1. Потребуется техническое заключение о допустимости и безопасности.\n"
            "2. В некоторых случаях возможны штрафы от ГЖИ.\n"
            "3. Мы поможем минимизировать риски и узаконить изменения «под ключ».\n\n"
            "Наш эксперт уже изучает вашу заявку."
        )
    else:
        final_text = (
            "📋 <b>Чек-лист для планируемой перепланировки:</b>\n\n"
            "1. <b>ЕГРН</b> — подтверждение собственности.\n"
            "2. <b>Техпаспорт БТИ</b> — исходная планировка.\n"
            "3. <b>Проект + Техзаключение</b> — для согласования.\n"
            "4. <b>Согласие</b> всех собственников.\n\n"
            "<i>Соблюдение порядка сэкономит вам до 3-х месяцев времени.</i>"
        )

    # Кнопка для записи на консультацию
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Записаться на экспертную консультацию", url="https://t.me/torion_expert")]
        ]
    )

    await message.answer(final_text, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    await message.answer("Выберите удобное время для звонка или напишите нашему эксперту напрямую:", reply_markup=markup)

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

    await message.answer("Спасибо! Наш эксперт свяжется с вами для анализа.")
    await state.clear()
