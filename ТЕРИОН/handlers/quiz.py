from aiogram import Router, F
from aiogram.types import Message, ContentType, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from config import LEADS_GROUP_CHAT_ID, QUIZ_THREAD_ID
from keyboards.main_menu import get_remodeling_status_keyboard

router = Router()


class QuizOrder(StatesGroup):
    """7-этапный квиз для сбора заявок"""
    city = State()        # 1. Город (текст)
    obj_type = State()    # 2. Тип объекта (кнопки)
    floor = State()       # 3. Этажность (текст - цифра)
    area = State()        # 4. Площадь (текст)
    status = State()      # 5. Статус перепланировки (кнопки)
    description = State() # 6. Описание изменений (текст)
    plan = State()        # 7. План помещения (фото/PDF или "Нет плана")


def get_object_type_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура выбора типа объекта"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏠 Квартира")],
            [KeyboardButton(text="🏢 Коммерция")],
            [KeyboardButton(text="🏡 Дом")]
        ],
        resize_keyboard=True
    )


@router.message(QuizOrder.city)
async def ask_city(message: Message, state: FSMContext):
    """1. Сохраняем город и переходим к типу объекта"""
    await state.update_data(city=message.text)
    await state.set_state(QuizOrder.obj_type)
    await message.answer(
        "Какой тип объекта?",
        reply_markup=get_object_type_keyboard()
    )


@router.message(QuizOrder.obj_type)
async def ask_obj_type(message: Message, state: FSMContext):
    """2. Сохраняем тип объекта и переходим к этажности"""
    obj_type = message.text
    # Нормализуем тип объекта
    if "квартира" in obj_type.lower():
        obj_type = "Квартира"
    elif "коммерц" in obj_type.lower():
        obj_type = "Коммерция"
    elif "дом" in obj_type.lower():
        obj_type = "Дом"
    
    await state.update_data(obj_type=obj_type)
    await state.set_state(QuizOrder.floor)
    await message.answer(
        "Какая этажность дома? (просто напишите цифру, например: 9, 16, 25)",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True)
    )


@router.message(QuizOrder.floor)
async def ask_floor(message: Message, state: FSMContext):
    """3. Сохраняем этажность и переходим к площади"""
    if message.text == "⬅️ Назад":
        await state.set_state(QuizOrder.obj_type)
        await message.answer(
            "Какой тип объекта?",
            reply_markup=get_object_type_keyboard()
        )
        return
    
    await state.update_data(floor=message.text)
    await state.set_state(QuizOrder.area)
    await message.answer(
        "Какая площадь объекта в кв.м.? (просто напишите число)",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True)
    )


@router.message(QuizOrder.area)
async def ask_area(message: Message, state: FSMContext):
    """4. Сохраняем площадь и переходим к статусу перепланировки"""
    if message.text == "⬅️ Назад":
        await state.set_state(QuizOrder.floor)
        await message.answer(
            "Какая этажность дома? (просто напишите цифру)",
            reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True)
        )
        return
    
    await state.update_data(area=message.text)
    await state.set_state(QuizOrder.status)
    await message.answer(
        "Какой статус перепланировки?",
        reply_markup=get_remodeling_status_keyboard()
    )


@router.message(QuizOrder.status)
async def ask_status(message: Message, state: FSMContext):
    """5. Сохраняем статус и переходим к описанию"""
    status = message.text
    # Нормализуем статус
    if "выполнена" in status.lower():
        status = "Выполнена"
    elif "планируется" in status.lower():
        status = "Планируется"
    elif "процесс" in status.lower():
        status = "В процессе"
    
    await state.update_data(status=status)
    await state.set_state(QuizOrder.description)
    await message.answer(
        "Опишите, какие изменения вы хотите внести или уже внесли в планировку?",
        reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅️ Назад")]], resize_keyboard=True)
    )


@router.message(QuizOrder.description)
async def ask_description(message: Message, state: FSMContext):
    """6. Сохраняем описание и переходим к плану помещения"""
    if message.text == "⬅️ Назад":
        await state.set_state(QuizOrder.status)
        await message.answer(
            "Какой статус перепланировки?",
            reply_markup=get_remodeling_status_keyboard()
        )
        return
    
    await state.update_data(description=message.text)
    await state.set_state(QuizOrder.plan)
    await message.answer(
        "Прикрепите план помещения (фото или PDF) или напишите «Нет плана», если его нет."
    )


@router.message(QuizOrder.plan)
async def ask_plan(message: Message, state: FSMContext):
    """7. Финальный этап - обрабатываем план и завершаем квиз"""
    data = await state.get_data()
    user_name = data.get('user_name', 'Клиент')
    phone = data.get('phone', 'Не указан')
    
    # Сохраняем информацию о плане
    plan_info = "План загружен"
    if message.text and message.text.lower() == "нет плана":
        plan_info = "Нет плана"
    elif message.document:
        plan_info = f"Документ: {message.document.file_name}"
    elif message.photo:
        plan_info = "Фото загружено"
    elif message.text:
        plan_info = message.text
    
    await state.update_data(plan=plan_info)
    
    # Формируем сводку для рабочей группы
    summary = (
        f"🔥 Новая заявка от {user_name} ({phone})!\n\n"
        f"📍 Город: {data.get('city')}\n"
        f"🏠 Тип объекта: {data.get('obj_type')}\n"
        f"📏 Площадь: {data.get('area')} кв.м.\n"
        f"🪜 Этажность: {data.get('floor')}\n"
        f"📅 Статус: {data.get('status')}\n"
        f"📝 Описание: {data.get('description')}\n"
        f"📄 План: {plan_info}"
    )
    
    # Отправляем в рабочую группу с thread_id
    try:
        await message.bot.send_message(
            chat_id=LEADS_GROUP_CHAT_ID,
            message_thread_id=int(QUIZ_THREAD_ID),
            text=summary
        )
    except Exception as e:
        # Если thread_id не работает, отправляем без него
        await message.bot.send_message(
            chat_id=LEADS_GROUP_CHAT_ID,
            text=summary
        )
    
    # Финальный текст пользователю
    FINAL_TEXT = (
        f"{user_name}, спасибо! Я отправил эксперту компании ТЕРИОН полученную от вас информацию.\n"
        "Мы свяжемся с вами в рабочее время с 9:00 до 20:00 по МСК.\n\n"
        "Если у вас остались вопросы или вы хотите отправить дополнительные документы, "
        "вы можете оставить информацию в чате — я всё передам специалисту."
    )
    
    await message.answer(FINAL_TEXT)
    await state.clear()


@router.message(F.photo | F.document)
async def handle_media(message: Message, state: FSMContext):
    """Обработка фото/файлов в последнем вопросе"""
    if await state.get_state() == QuizOrder.plan:
        await ask_plan(message, state)
    else:
        await message.answer("Пожалуйста, ответьте на текущий вопрос.")
