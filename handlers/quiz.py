import logging
import os
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardRemove, FSInputFile
from database.db import db
from keyboards.main_menu import get_object_type_keyboard, get_remodeling_status_keyboard
from services.lead_service import send_lead_to_admin_group
from utils.voice_handler import transcribe

router = Router()

class QuizOrder(StatesGroup):
    city = State()
    object_type = State()
    floor = State()
    area = State()
    status = State()
    description = State()
    bti_file = State()

# STAGE_LOGIC: 1. City
@router.message(QuizOrder.city)
async def process_city(message: Message, state: FSMContext):
    text = message.text
    if message.voice:
        text = await transcribe(message.voice.file_id)

    if not text:
        await message.answer("Пожалуйста, введите город текстом или голосом.")
        return

    await state.update_data(city=text)
    await state.set_state(QuizOrder.object_type)
    await message.answer("2. Тип объекта (Квартира/Коммерция):", reply_markup=get_object_type_keyboard())

# STAGE_LOGIC: 2. Object Type
@router.message(QuizOrder.object_type)
async def process_object_type(message: Message, state: FSMContext):
    if message.text not in ["Квартира", "Коммерция"]:
        await message.answer("Пожалуйста, выберите тип объекта из списка.", reply_markup=get_object_type_keyboard())
        return

    await state.update_data(object_type=message.text)
    await state.set_state(QuizOrder.floor)
    await message.answer("3. Укажите этаж:", reply_markup=ReplyKeyboardRemove())

# STAGE_LOGIC: 3. Floor
@router.message(QuizOrder.floor)
async def process_floor(message: Message, state: FSMContext):
    text = message.text
    if message.voice:
        text = await transcribe(message.voice.file_id)

    await state.update_data(floor=text)
    await state.set_state(QuizOrder.area)
    await message.answer("4. Какая площадь объекта (кв. м)?")

# STAGE_LOGIC: 4. Area
@router.message(QuizOrder.area)
async def process_area(message: Message, state: FSMContext):
    text = message.text
    if message.voice:
        text = await transcribe(message.voice.file_id)

    try:
        area_val = float(text.replace(',', '.').split()[0])
        await state.update_data(area=area_val)
    except:
        await state.update_data(area=text) # Keep as text if conversion fails

    await state.set_state(QuizOrder.status)
    await message.answer("5. Статус перепланировки (Планируется/Выполнена):", reply_markup=get_remodeling_status_keyboard())

# STAGE_LOGIC: 5. Status
@router.message(QuizOrder.status)
async def process_status(message: Message, state: FSMContext):
    if message.text not in ["Планируется", "Выполнена"]:
        await message.answer("Пожалуйста, выберите статус.", reply_markup=get_remodeling_status_keyboard())
        return

    await state.update_data(status=message.text)
    await state.set_state(QuizOrder.description)
    await message.answer("6. Описание изменений (что планируете или уже сделали):", reply_markup=ReplyKeyboardRemove())

# STAGE_LOGIC: 6. Description
@router.message(QuizOrder.description)
async def process_description(message: Message, state: FSMContext):
    text = message.text
    if message.voice:
        text = await transcribe(message.voice.file_id)

    await state.update_data(description=text)
    await state.set_state(QuizOrder.bti_file)
    await message.answer("7. Загрузите файл планировки или фото БТИ (если есть, иначе отправьте '-')")

# STAGE_LOGIC: 7. File & Finish
@router.message(QuizOrder.bti_file)
async def process_bti_file(message: Message, state: FSMContext):
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id

    data = await state.get_data()
    user_id = message.from_user.id

    # Update lead in DB
    db.update_lead(user_id, {
        "city": data.get("city"),
        "object_type": data.get("object_type"),
        "floor": data.get("floor"),
        "area": data.get("area"),
        "status": data.get("status"),
        "description": data.get("description"),
        "bti_file": file_id
    })

    # Send to admin
    await send_lead_to_admin_group(message.bot, user_id, data, file_id)

    # Final message logic
    if data.get("status") == "Выполнена":
        final_text = "Спасибо! Ваша заявка принята. Так как перепланировка уже выполнена, наш специалист свяжется с вами, чтобы обсудить варианты её узаконивания."
    else:
        final_text = "Спасибо! Ваша заявка принята. Мы изучим ваши пожелания и предложим оптимальный вариант проекта и согласования."

    await message.answer(final_text, reply_markup=ReplyKeyboardRemove())
    await state.clear()
