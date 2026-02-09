"""
Квиз для сбора заявок на перепланировку (FSM).
7 этапов: Контакт → Город → Тип объекта → Этажность → Площадь → Статус → Описание → План
"""
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from database import db
from config import GROUP_ID, THREAD_ID_LEADS

router = Router()

# === FSM STATES ===
class QuizStates(StatesGroup):
    greeting = State()           # Приветствие + согласие
    contact = State()            # Запрос контакта
    city = State()              # Город
    object_type = State()        # Тип объекта
    floors = State()             # Этажность
    area = State()               # Площадь
    status = State()            # Статус перепланировки
    description = State()        # Описание
    plan = State()              # План помещения

# === KEYBOARDS ===
def get_contact_keyboard():
    """Кнопка отправки контакта (request_contact=True)"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить контакт и согласиться", request_contact=True)]],
        resize_keyboard=True
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

# === START QUIZ ===
@router.message(F.text.startswith("/start"))
async def start_quiz(message: Message, state: FSMContext):
    """Начало квиза - приветствие + согласие"""
    await message.answer(
        "🏢 <b>Вас приветствует компания ТЕРИОН!</b>\n\n"
        "Я — Антон, ваш ИИ-помощник по перепланировкам.\n\n"
        "Нажимая кнопку ниже, вы даете согласие на обработку "
        "персональных данных, получение уведомлений и информационную переписку.\n\n"
        "📞 Все консультации носят информационный характер, "
        "финальное решение подтверждает эксперт ТЕРИОН.",
        reply_markup=get_contact_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(QuizStates.greeting)

# === GREETING -> CONTACT ===
@router.message(QuizStates.greeting, F.contact)
async def process_contact(message: Message, state: FSMContext):
    """Обработка контакта - сразу переходим к вопросам"""
    user_name = message.from_user.full_name or message.from_user.first_name
    phone = message.contact.phone_number
    
    # Сохраняем контакт
    await db.add_lead(
        user_id=message.from_user.id,
        name=user_name,
        phone=phone
    )
    
    await message.answer(
        f"✅ <b>{user_name}</b>, спасибо!\n\n"
        "🏙️ <b>1. В каком городе находится объект?</b>",
        parse_mode="HTML"
    )
    await state.set_state(QuizStates.city)

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
    object_type = message.text.split()[1]
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
    floors = message.text.strip()
    await state.update_data(floors=floors)
    
    await message.answer(
        f"🏢 <b>Этажность: {floors} этажей</b>\n\n"
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
    status = message.text.split()[1]
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

# === PLAN ===
@router.message(QuizStates.plan)
async def process_plan(message: Message, state: FSMContext):
    """План помещения"""
    if message.text and message.text.lower() in ["нет плана", "❌ нет плана"]:
        plan = "Нет плана"
        has_plan_photo = False
    elif message.photo:
        plan = message.photo[-1].file_id
        has_plan_photo = True
    else:
        plan = message.text.strip() if message.text else "Нет плана"
        has_plan_photo = False
    
    await state.update_data(plan=plan, has_plan_photo=has_plan_photo)
    await finish_quiz(message, state)

async def finish_quiz(message: Message, state: FSMContext):
    """Завершение квиза"""
    data = await state.get_data()
    user_name = message.from_user.full_name or message.from_user.first_name
    
    # Формируем сообщение в группу
    lead_text = (
        f"🔥 <b>Новая заявка!</b>\n\n"
        f"👤 <b>Клиент:</b> {user_name}\n"
        f"📍 <b>Город:</b> {data.get('city', 'Не указан')}\n"
        f"🏠 <b>Тип объекта:</b> {data.get('object_type', 'Не указан')}\n"
        f"🔢 <b>Этажность:</b> {data.get('floors', 'Не указана')}\n"
        f"📐 <b>Площадь:</b> {data.get('area', 'Не указана')} кв.м.\n"
        f"📋 <b>Статус:</b> {data.get('status', 'Не указан')}\n\n"
        f"📝 <b>Описание:</b>\n{data.get('description', 'Нет описания')}\n\n"
        f"🏗️ <b>План:</b> {'Есть фото' if data.get('has_plan_photo') else data.get('plan', 'Нет')}"
    )
    
    # Отправляем в группу
    try:
        from main import bot
        if data.get('has_plan_photo') and data.get('plan'):
            await bot.send_photo(
                chat_id=GROUP_ID,
                message_thread_id=THREAD_ID_LEADS,
                photo=data['plan'],
                caption=lead_text,
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                chat_id=GROUP_ID,
                message_thread_id=THREAD_ID_LEADS,
                text=lead_text,
                parse_mode="HTML"
            )
    except Exception as e:
        print(f"Ошибка отправки в группу: {e}")
    
    # Ответ пользователю
    await message.answer(
        f"✅ <b>{user_name}</b>, спасибо!\n\n"
        f"📤 Я отправил эксперту компании ТЕРИОН полученную от вас информацию.\n\n"
        f"⏰ Мы свяжемся с вами в рабочее время с 9:00 до 20:00 по МСК.\n\n"
        f"❓ Если у вас остались вопросы или вы хотите отправить дополнительные документы, "
        f"вы можете оставить информацию в чате — я всё передам специалисту.",
        parse_mode="HTML"
    )
    
    # Сохраняем в БД
    await db.update_lead_status(
        user_id=message.from_user.id,
        status="quiz_completed",
        data=data
    )
    
    await state.clear()
