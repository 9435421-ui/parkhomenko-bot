from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
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


def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков квиза"""
    
    @dp.callback_query_handler(lambda c: c.data == "mode:quiz")
    async def start_quiz_callback(callback: types.CallbackQuery, state: FSMContext):
        """Начало квиза через callback"""
        await state.finish()
        await db.update_user_state(callback.from_user.id, mode="quiz")
        await state.set_state(QuizOrder.extra_contact)
        await callback.message.answer(
            "📝 Начинаем опрос для подготовки анализа вашей ситуации.\n\n"
            "Шаг 1: Если у вас есть дополнительный способ связи (WhatsApp/почта/другой номер) — напишите его, или отправьте «нет».",
            reply_markup=types.ReplyKeyboardRemove()
        )
        await callback.answer()
    
    @dp.message_handler(state=QuizOrder.extra_contact)
    async def process_extra_contact(message: types.Message, state: FSMContext):
        contact = message.text if message.text.lower() != "нет" else None
        await state.update_data(extra_contact=contact)
        await state.set_state(QuizOrder.object_type)
        await message.answer(
            "Шаг 2: Выберите тип объекта:",
            reply_markup=get_object_type_keyboard()
        )
    
    @dp.callback_query_handler(lambda c: c.data.startswith("obj:"), state=QuizOrder.object_type)
    async def process_object_type(callback: types.CallbackQuery, state: FSMContext):
        obj_type = callback.data.split(":")[1]
        await state.update_data(object_type=obj_type)
        
        if obj_type == "dom":
            await state.set_state(QuizOrder.house_material)
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(
                types.InlineKeyboardButton(text="Кирпич", callback_data="mat:kirpich"),
                types.InlineKeyboardButton(text="Брус", callback_data="mat:brus"),
                types.InlineKeyboardButton(text="Каркас", callback_data="mat:karkas"),
                types.InlineKeyboardButton(text="Пеноблок", callback_data="mat:penoblok"),
                types.InlineKeyboardButton(text="Другое", callback_data="mat:other")
            )
            await callback.message.edit_text("Шаг 2.5: Выберите материал дома:", reply_markup=kb)
        elif obj_type == "kommercia":
            await state.set_state(QuizOrder.commercial_purpose)
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(
                types.InlineKeyboardButton(text="Общепит", callback_data="purp:food"),
                types.InlineKeyboardButton(text="Торговля", callback_data="purp:trade"),
                types.InlineKeyboardButton(text="Офис", callback_data="purp:office"),
                types.InlineKeyboardButton(text="Медицина", callback_data="purp:med"),
                types.InlineKeyboardButton(text="Другое", callback_data="purp:other")
            )
            await callback.message.edit_text("Шаг 2.5: Выберите назначение помещения:", reply_markup=kb)
        else: # Квартира
            await state.set_state(QuizOrder.city)
            await callback.message.edit_text("Шаг 3: В каком городе/регионе находится объект?")
        await callback.answer()
    
    @dp.callback_query_handler(lambda c: c.data.startswith("mat:"), state=QuizOrder.house_material)
    async def process_house_material(callback: types.CallbackQuery, state: FSMContext):
        material = callback.data.split(":")[1]
        await state.update_data(house_material=material)
        await state.set_state(QuizOrder.city)
        await callback.message.edit_text("Шаг 3: В каком городе/регионе находится объект?")
        await callback.answer()
    
    @dp.callback_query_handler(lambda c: c.data.startswith("purp:"), state=QuizOrder.commercial_purpose)
    async def process_commercial_purpose(callback: types.CallbackQuery, state: FSMContext):
        purpose = callback.data.split(":")[1]
        await state.update_data(commercial_purpose=purpose)
        await state.set_state(QuizOrder.city)
        await callback.message.edit_text("Шаг 3: В каком городе/регионе находится объект?")
        await callback.answer()
    
    @dp.message_handler(state=QuizOrder.city)
    async def process_city(message: types.Message, state: FSMContext):
        await state.update_data(city=message.text)
        await state.set_state(QuizOrder.floor_info)
        await message.answer("Шаг 4: На каком этаже находится объект? (например: 5/9 - 5-й этаж из 9)")
    
    @dp.message_handler(state=QuizOrder.floor_info)
    async def process_floor(message: types.Message, state: FSMContext):
        await state.update_data(floor_info=message.text)
        await state.set_state(QuizOrder.remodeling_status)
        await message.answer(
            "Шаг 5: Какой статус перепланировки?",
            reply_markup=get_remodeling_status_keyboard()
        )
    
    @dp.callback_query_handler(lambda c: c.data.startswith("remodel:"), state=QuizOrder.remodeling_status)
    async def process_remodeling_status(callback: types.CallbackQuery, state: FSMContext):
        status = callback.data.split(":")[1]
        await state.update_data(remodeling_status=status)
        await state.set_state(QuizOrder.change_plan)
        await callback.message.edit_text(
            "Шаг 6: Что планируется изменить?\n"
            "(например: снести стену, объединить санузел, перенести кухню)"
        )
        await callback.answer()
    
    @dp.message_handler(state=QuizOrder.change_plan)
    async def process_change_plan(message: types.Message, state: FSMContext):
        await state.update_data(change_plan=message.text)
        await state.set_state(QuizOrder.bti_status)
        await message.answer(
            "Шаг 7: Есть ли техпаспорт БТИ?",
            reply_markup=get_bti_documents_keyboard()
        )
    
    @dp.callback_query_handler(lambda c: c.data.startswith("bti:"), state=QuizOrder.bti_status)
    async def finish_quiz(callback: types.CallbackQuery, state: FSMContext):
        bti = callback.data.split(":")[1]
        await state.update_data(bti_status=bti)
        
        # Получаем все данные
        data = await state.get_data()
        
        # Сохраняем лид
        try:
            lead_data = {
                "extra_contact": data.get("extra_contact"),
                "object_type": data.get("object_type"),
                "house_material": data.get("house_material"),
                "commercial_purpose": data.get("commercial_purpose"),
                "city": data.get("city"),
                "floor_info": data.get("floor_info"),
                "remodeling_status": data.get("remodeling_status"),
                "change_plan": data.get("change_plan"),
                "bti_status": data.get("bti_status"),
            }
            
            lead_id = await db.add_lead(
                user_id=callback.from_user.id,
                name=callback.from_user.full_name,
                phone=data.get("extra_contact", ""),
                **lead_data
            )
            
            # Отправляем в группу
            if ADMIN_GROUP_ID:
                await lead_service.send_lead_to_group(
                    bot=callback.bot,
                    chat_id=ADMIN_GROUP_ID,
                    lead_data=lead_data,
                    user_id=callback.from_user.id
                )
            
            await callback.message.edit_text(
                "✅ <b>Заявка принята!</b>\n\n"
                "Мы проанализируем вашу ситуацию и свяжемся с вами.\n"
                "Обычно это занимает 1-2 рабочих дня.",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка сохранения лида: {e}")
            await callback.message.edit_text(
                "❌ Произошла ошибка при сохранении заявки.\n"
                "Пожалуйста, попробуйте позже или свяжитесь с нами напрямую."
            )
        
        await state.finish()
        await callback.answer()
