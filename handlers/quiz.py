"""
Квиз для сбора заявок на перепланировку (FSM).
Логика: Старт -> Greeting (кнопка контакта) -> Contact -> Город -> ... -> План
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from database import db
from config import LEADS_GROUP_CHAT_ID, THREAD_ID_KVARTIRY, THREAD_ID_KOMMERCIA, THREAD_ID_DOMA

router = Router()

# === FSM STATES ===
class QuizStates(StatesGroup):
    greeting = State()        # Приветствие - ожидаем контакт
    contact = State()         # Контакт получен (для обратной совместимости)
    city = State()            # Город
    object_type = State()     # Тип объекта
    floors = State()          # Этажность
    area = State()            # Площадь
    status = State()          # Статус перепланировки
    description = State()      # Описание
    plan = State()            # План помещения

# === KEYBOARDS ===
def get_contact_keyboard():
    """Кнопка отправки контакта + согласие"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить контакт и согласиться", request_contact=True)]],
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


# === GREETING -> CONTACT ===
@router.message(QuizStates.greeting, F.contact)
async def process_contact(message: Message, state: FSMContext):
    """Ловим контакт - сохраняем и переходим к вопросам"""
    user_name = message.from_user.full_name or message.from_user.first_name or "Клиент"
    phone = message.contact.phone_number
    
    # Сохраняем в state
    await state.update_data(user_name=user_name, phone=phone)
    
    # Убираем кнопку контакта
    await message.answer(
        f"✅ {user_name}, приятно познакомиться!\n"
        f"Телефон {phone} получен.\n\n"
        "Для первичного анализа вашего объекта ответьте на несколько вопросов:",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Первый вопрос
    await message.answer(
        "🏙️ <b>1. В каком городе находится объект?</b>",
        parse_mode="HTML"
    )
    await state.set_state(QuizStates.city)


# === GREETING - ЛЮБОЙ ДРУГОЙ ВВОД ===
@router.message(QuizStates.greeting)
async def process_greeting_fallback(message: Message, state: FSMContext):
    """Fallback - если не контакт"""
    await message.answer(
        "📱 <b>Пожалуйста, нажмите кнопку ниже</b>\n\n"
        "«📱 Отправить контакт и согласиться»",
        reply_markup=get_contact_keyboard()
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
async def process_plan(message: Message, state: FSMContext, bot: Bot):
    """План помещения - завершение квиза"""
    data = await state.get_data()
    user_name = data.get('user_name', "Клиент")
    phone = data.get('phone', "Не указан")
    
    # Определяем что прислал пользователь
    if message.photo:
        photo_id = message.photo[-1].file_id
        plan_text = "План загружен"
        has_photo = True
    elif message.text and message.text.lower() in ["нет плана", "❌ нет плана", "нет"]:
        photo_id = None
        plan_text = "Нет плана"
        has_photo = False
    elif message.text:
        photo_id = None
        plan_text = message.text.strip()
        has_photo = False
    else:
        photo_id = None
        plan_text = "Нет плана"
        has_photo = False
    
    # Thread ID по типу объекта
    object_type = data.get('object_type', '')
    thread_id = get_thread_id(object_type)
    
    # Отправляем уведомление о новом контакте
    try:
        await bot.send_message(
            chat_id=LEADS_GROUP_CHAT_ID,
            message_thread_id=THREAD_ID_KVARTIRY,
            text=f"📱 <b>Новый контакт!</b>\n👤 {user_name}\n📞 {phone}",
            parse_mode="HTML"
        )
    except:
        pass
    
    # Формируем заявку
    lead_text = (
        f"🔥 <b>Новая заявка!</b>\n\n"
        f"👤 <b>Клиент:</b> {user_name}\n"
        f"📞 <b>Телефон:</b> {phone}\n"
        f"📍 <b>Город:</b> {data.get('city', 'Не указан')}\n"
        f"🏠 <b>Тип объекта:</b> {data.get('object_type', 'Не указан')}\n"
        f"🔢 <b>Этажность:</b> {data.get('floors', 'Не указана')}\n"
        f"📐 <b>Площадь:</b> {data.get('area', 'Не указана')} кв.м.\n"
        f"📋 <b>Статус:</b> {data.get('status', 'Не указан')}\n\n"
        f"📝 <b>Описание:</b>\n{data.get('description', 'Нет описания')}\n\n"
        f"🏗️ <b>План:</b> {plan_text}"
    )
    
    # Отправляем заявку
    try:
        if has_photo and photo_id:
            await bot.send_photo(
                chat_id=LEADS_GROUP_CHAT_ID,
                message_thread_id=thread_id,
                photo=photo_id,
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
        print(f"✅ Заявка от {user_name} отправлена в thread {thread_id}")
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
    
    # Ответ пользователю
    await message.answer(
        f"✅ <b>{user_name}</b>, спасибо!\n\n"
        f"📤 Я отправил эксперту компании ТЕРИОН полученную от вас информацию.\n\n"
        f"⏰ Мы свяжемся с вами в рабочее время с 9:00 до 20:00 по МСК.\n\n"
        f"❓ Если у вас остались вопросы, вы можете оставить сообщение.",
        parse_mode="HTML"
    )
    
    # Сохраняем в БД
    await db.add_lead(
        user_id=message.from_user.id,
        name=user_name,
        phone=phone,
        city=data.get('city', ''),
        object_type=data.get('object_type', ''),
        floors=data.get('floors', ''),
        area=data.get('area', ''),
        remodeling_status=data.get('status', ''),
        change_plan=data.get('description', '')
    )
    
    await state.clear()
