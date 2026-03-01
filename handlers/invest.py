"""
Обработчик инвест-калькулятора
aiogram 3.x версия
"""
from aiogram import Router, F, Dispatcher
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from database.db import db
from config import ADMIN_GROUP_ID
import json
import logging

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "mode:invest")
async def start_invest_mode(callback: CallbackQuery, state: FSMContext):
    """Переход в режим инвест-калькулятора"""
    await state.clear()
    await db.update_user_state(callback.from_user.id, mode="invest")
    await callback.message.answer(
        "💰 <b>Инвест-калькулятор</b>\n\n"
        "Этот инструмент поможет вам оценить инвестиционный потенциал вашей недвижимости.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(F.web_app_data)
async def handle_web_app_data(message: Message):
    """Обработка данных из Mini App"""
    try:
        data = json.loads(message.web_app_data.data)
        await message.answer("✅ Данные получены! Мы свяжемся с вами.")
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.answer("❌ Ошибка обработки данных")


def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков инвест-режима"""
    dp.include_router(router)
