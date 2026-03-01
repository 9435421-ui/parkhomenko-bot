from aiogram import Router, F, Dispatcher
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
    house_material = State()
    commercial_purpose = State()
    city = State()
    floor_info = State()
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


def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков квиза"""
    dp.include_router(quiz_router)
