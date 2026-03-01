from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from config import ADMIN_GROUP_ID
from datetime import datetime, time
from database.db import db
from services.lead_service import lead_service
from keyboards.main_menu import (
    get_object_type_keyboard,
    get_remodeling_status_keyboard,
    get_bti_documents_keyboard,
    get_main_menu
)
import logging

logger = logging.getLogger(__name__)
quiz_router = Router()

class QuizOrder(StatesGroup):
    extra_contact = State()
    object_type = State()
    house_material = State()      # Для домов
    commercial_purpose = State()  # Для коммерции
    city = State()
    floor_info = State()          # Этаж/Этажность
    remodeling_status = State()
    change_plan = State()
    bti_status = State()

@quiz_router.callback_query(F.data == "mode:quiz")
async def start_quiz_callback(callback: CallbackQuery, state: FSMContext):
    """Начало квиза через callback"""
    await state.clear()
    await db.update_user_state(callback.from_user.id, mode="quiz")
    await state.set_state(QuizOrder.extra_contact)
    await callback.message.answer(
        "📝 Начинаем опрос для подготовки анализа вашей ситуации.\n\n"
        "Шаг 1: Если у вас есть дополнительный способ связи (WhatsApp/почта/другой номер) — напишите его, или отправьте «нет».",
        reply_markup=ReplyKeyboardRemove()
    )
    await callback.answer()

@quiz_router.message(QuizOrder.extra_contact)
async def process_extra_contact(message: Message, state: FSMContext):
    contact = message.text if message.text.lower() != "нет" else None
    await state.update_data(extra_contact=contact)
    await state.set_state(QuizOrder.object_type)
    await message.answer(
        "Шаг 2: Выберите тип объекта:",
        reply_markup=get_object_type_keyboard()
    )

@quiz_router.callback_query(QuizOrder.object_type, F.data.startswith("obj:"))
async def process_object_type(callback: CallbackQuery, state: FSMContext):
    obj_type = callback.data.split(":")[1]
    await state.update_data(object_type=obj_type)
    
    if obj_type == "dom":
        await state.set_state(QuizOrder.house_material)
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Кирпич", callback_data="mat:kirpich")],
            [InlineKeyboardButton(text="Брус", callback_data="mat:brus")],
            [InlineKeyboardButton(text="Каркас", callback_data="mat:karkas")],
            [InlineKeyboardButton(text="Пеноблок", callback_data="mat:penoblok")],
            [InlineKeyboardButton(text="Другое", callback_data="mat:other")]
        ])
        await callback.message.edit_text("Шаг 2.5: Выберите материал дома:", reply_markup=kb)
    elif obj_type == "kommercia":
        await state.set_state(QuizOrder.commercial_purpose)
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Общепит", callback_data="purp:food")],
            [InlineKeyboardButton(text="Торговля", callback_data="purp:trade")],
            [InlineKeyboardButton(text="Офис", callback_data="purp:office")],
            [InlineKeyboardButton(text="Медицина", callback_data="purp:med")],
            [InlineKeyboardButton(text="Другое", callback_data="purp:other")]
        ])
        await callback.message.edit_text("Шаг 2.5: Выберите назначение помещения:", reply_markup=kb)
    else: # Квартира
        await state.set_state(QuizOrder.city)
        await callback.message.edit_text("Шаг 3: В каком городе/регионе находится объект?")
    await callback.answer()

@quiz_router.callback_query(QuizOrder.house_material, F.data.startswith("mat:"))
async def process_house_material(callback: CallbackQuery, state: FSMContext):
    material = callback.data.split(":")[1]
    await state.update_data(house_material=material)
    await state.set_state(QuizOrder.city)
    await callback.message.edit_text("Шаг 3: В каком городе/регионе находится объект?")
    await callback.answer()

@quiz_router.callback_query(QuizOrder.commercial_purpose, F.data.startswith("purp:"))
async def process_commercial_purpose(callback: CallbackQuery, state: FSMContext):
    purpose = callback.data.split(":")[1]
    await state.update_data(commercial_purpose=purpose)
    await state.set_state(QuizOrder.city)
    await callback.message.edit_text("Шаг 3: В каком городе/регионе находится объект?")
    await callback.answer()

@quiz_router.message(QuizOrder.city)
async def process_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(QuizOrder.floor_info)
    await message.answer("Шаг 4: Укажите этаж и общую этажность дома (например: 5/9):")

@quiz_router.message(QuizOrder.floor_info)
async def process_floor(message: Message, state: FSMContext):
    await state.update_data(floor_info=message.text)
    await state.set_state(QuizOrder.remodeling_status)
    await message.answer(
        "Шаг 5: Статус перепланировки:",
        reply_markup=get_remodeling_status_keyboard()
    )

@quiz_router.callback_query(QuizOrder.remodeling_status, F.data.startswith("remodel:"))
async def process_remodeling_status(callback: CallbackQuery, state: FSMContext):
    status = callback.data.split(":")[1]
    await state.update_data(remodeling_status=status)
    await state.set_state(QuizOrder.change_plan)
    await callback.message.edit_text("Шаг 6: Опишите планируемые или уже выполненные изменения:")
    await callback.answer()

@quiz_router.message(QuizOrder.change_plan)
async def process_change_plan(message: Message, state: FSMContext):
    await state.update_data(change_plan=message.text)
    await state.set_state(QuizOrder.bti_status)
    await message.answer(
        "Шаг 7: Статус документов БТИ:",
        reply_markup=get_bti_documents_keyboard()
    )

@quiz_router.callback_query(QuizOrder.bti_status, F.data.startswith("bti:"))
async def finish_quiz(callback: CallbackQuery, state: FSMContext):
    bti = callback.data.split(":")[1]
    await state.update_data(bti_status=bti)
    data = await state.get_data()
    user = callback.from_user
    
    # Отправка лида через сервис (с распределением по топикам)
    lead_data = {
        'name': user.full_name,
        'phone': user.username or f"id{user.id}",
        'extra_contact': data.get('extra_contact'),
        'object_type': data.get('object_type'),
        'city': data.get('city'),
        'floor_info': data.get('floor_info'),
        'remodeling_status': data.get('remodeling_status'),
        'change_plan': data.get('change_plan'),
        'bti_status': bti
    }
    
    await lead_service.send_lead_to_group(callback.bot, lead_data, user.id)

    # Сохранение в БД
    await db.add_lead(
        user_id=user.id,
        name=user.full_name,
        phone=data.get('extra_contact') or "",
        object_type=data.get('object_type'),
        city=data.get('city'),
        status=data.get('remodeling_status'),
        details=data.get('change_plan')
    )

    await callback.message.edit_text(
        "✅ Спасибо! Ваша заявка принята.\n\n"
        "Юлия Пархоменко свяжется с вами в ближайшее время для детального анализа.\n"
        "Обычно это занимает от 30 минут до 2 часов в рабочее время.",
        reply_markup=get_main_menu()
    )
    
    await state.clear()
    await db.update_user_state(user.id, mode="main")
    await callback.answer()
