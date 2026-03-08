from aiogram import Router, F, Dispatcher, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from config import LEADS_GROUP_CHAT_ID, THREAD_ID_HOT_LEADS
from database.db import db
import logging

logger = logging.getLogger(__name__)
quiz_router = Router()

class QuizOrder(StatesGroup):
    consent = State()
    city = State()
    object_type = State()
    floor_info = State()
    area = State()
    remodeling_status = State()
    description = State()
    plan = State()

@quiz_router.callback_query(F.data == "mode:quiz")
async def start_quiz_callback(callback: CallbackQuery, state: FSMContext):
    """Начало квиза v2.3 — Юридический блок"""
    await state.clear()
    
    text = (
        "Вас приветствует компания ТЕРИОН!\n"
        "Я — Антон, ваш ИИ-помощник. Нажимая кнопку ниже, вы даете согласие на обработку персональных данных, "
        "получение уведомлений и информационную переписку.\n"
        "Все консультации носят информационный характер, финальное решение подтверждает эксперт ТЕРИОН."
    )
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить контакт и согласиться", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await callback.message.answer(text, reply_markup=keyboard)
    await state.set_state(QuizOrder.consent)
    await callback.answer()

@quiz_router.message(QuizOrder.consent, F.contact)
async def process_consent(message: Message, state: FSMContext):
    """Получение контакта и персонализация"""
    contact = message.contact
    user_name = contact.first_name
    
    # Сохраняем контакт в БД
    await db.update_user_contact(message.from_user.id, contact.phone_number)
    await state.update_data(phone=contact.phone_number, name=user_name)
    
    text = f"{user_name}, приятно познакомиться! Для первичного анализа вашего объекта ответьте на несколько вопросов:"
    await message.answer(text, reply_markup=ReplyKeyboardRemove())
    
    await message.answer("1. В каком городе находится объект?")
    await state.set_state(QuizOrder.city)

@quiz_router.message(QuizOrder.city)
async def process_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Квартира"), KeyboardButton(text="Коммерция")],
            [KeyboardButton(text="Дом")]
        ],
        resize_keyboard=True
    )
    await message.answer("2. Выберите тип объекта:", reply_markup=keyboard)
    await state.set_state(QuizOrder.object_type)

@quiz_router.message(QuizOrder.object_type)
async def process_object_type(message: Message, state: FSMContext):
    await state.update_data(object_type=message.text)
    await message.answer("3. Укажите этаж и общую этажность дома (например, 5/17):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(QuizOrder.floor_info)

@quiz_router.message(QuizOrder.floor_info)
async def process_floor(message: Message, state: FSMContext):
    await state.update_data(floor_info=message.text)
    await message.answer("4. Какая общая площадь помещения (кв.м)?")
    await state.set_state(QuizOrder.area)

@quiz_router.message(QuizOrder.area)
async def process_area(message: Message, state: FSMContext):
    await state.update_data(area=message.text)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Планируется"), KeyboardButton(text="Уже сделана")],
            [KeyboardButton(text="В процессе")]
        ],
        resize_keyboard=True
    )
    await message.answer("5. Статус перепланировки:", reply_markup=keyboard)
    await state.set_state(QuizOrder.remodeling_status)

@quiz_router.message(QuizOrder.remodeling_status)
async def process_status(message: Message, state: FSMContext):
    await state.update_data(remodeling_status=message.text)
    await message.answer("6. Кратко опишите, какие изменения планируются или уже сделаны:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(QuizOrder.description)

@quiz_router.message(QuizOrder.description)
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("7. Прикрепите план помещения (фото, PDF) или отправьте текст «нет плана»:")
    await state.set_state(QuizOrder.plan)

@quiz_router.message(QuizOrder.plan)
async def process_plan(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    user_name = data.get('name', 'Клиент')
    
    # Обработка плана (фото/документ/текст)
    plan_info = "Прикреплен файл/фото"
    if message.text and message.text.lower() == "нет плана":
        plan_info = "План отсутствует"
    
    # Формируем отчет для группы
    report = (
        f"🎯 <b>НОВАЯ ЗАЯВКА (КВИЗ v2.3)</b>\n\n"
        f"👤 Имя: {user_name}\n"
        f"📞 Телефон: {data.get('phone')}\n"
        f"📍 Город: {data.get('city')}\n"
        f"🏢 Объект: {data.get('object_type')}\n"
        f"🔢 Этаж: {data.get('floor_info')}\n"
        f"📐 Площадь: {data.get('area')} кв.м\n"
        f"🛠 Статус: {data.get('remodeling_status')}\n"
        f"📝 Описание: {data.get('description')}\n"
        f"🗺 План: {plan_info}\n"
    )
    
    # Отправка в рабочую группу
    try:
        thread_id = int(THREAD_ID_HOT_LEADS) if THREAD_ID_HOT_LEADS else None
        await bot.send_message(LEADS_GROUP_CHAT_ID, report, parse_mode="HTML", message_thread_id=thread_id)
        
        # Если есть фото или документ, пересылаем их тоже
        if message.photo:
            await bot.send_photo(LEADS_GROUP_CHAT_ID, message.photo[-1].file_id, caption=f"План от {user_name}", message_thread_id=thread_id)
        elif message.document:
            await bot.send_document(LEADS_GROUP_CHAT_ID, message.document.file_id, caption=f"План от {user_name}", message_thread_id=thread_id)
            
    except Exception as e:
        logger.error(f"Ошибка отправки заявки в группу: {e}")

    # Финальный ответ пользователю по эталону
    final_text = (
        f"{user_name}, спасибо! Я отправлю эксперту компании ТЕРИОН, полученную от вас информацию.\n"
        f"Мы свяжемся с вами в рабочее время с 9:00 до 20:00 по МСК.\n"
        f"Если у вас остались вопросы или вы хотите отправить дополнительные документы, "
        f"вы можете оставить информацию в чате — я всё передам специалисту."
    )
    
    await message.answer(final_text, reply_markup=ReplyKeyboardRemove())
    await state.clear()

def register_handlers(dp: Dispatcher):
    dp.include_router(quiz_router)
