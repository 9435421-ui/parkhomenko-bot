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


from aiogram.fsm.state import StatesGroup, State

class InvestStates(StatesGroup):
    house_type = State()
    area = State()
    changes = State()

@router.callback_query(F.data == "mode:invest")
async def start_invest_mode(callback: CallbackQuery, state: FSMContext):
    """Переход в режим инвест-калькулятора (внутренний сценарий)"""
    await state.clear()
    await db.update_user_state(callback.from_user.id, mode="invest")
    await state.set_state(InvestStates.house_type)
    await callback.message.answer(
        "🧮 <b>Калькулятор перепланировки</b>\n\n"
        "Шаг 1: Укажите тип дома (например: панельный, кирпичный, монолитный):",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(InvestStates.house_type)
async def process_house_type(message: Message, state: FSMContext):
    await state.update_data(house_type=message.text)
    await state.set_state(InvestStates.area)
    await message.answer("Шаг 2: Укажите общую площадь объекта (кв.м.):")

@router.message(InvestStates.area)
async def process_area(message: Message, state: FSMContext):
    await state.update_data(area=message.text)
    await state.set_state(InvestStates.changes)
    await message.answer("Шаг 3: Опишите планируемые изменения (например: перенос кухни, объединение санузла):")

@router.message(InvestStates.changes)
async def process_changes(message: Message, state: FSMContext):
    data = await state.get_data()
    house_type = data.get("house_type")
    area = data.get("area")
    changes = message.text
    user = message.from_user
    
    # Формируем отчет для админа
    report = (
        "💰 <b>Новый расчет в калькуляторе</b>\n\n"
        f"👤 Пользователь: {user.full_name} (@{user.username})\n"
        f"🏠 Тип дома: {house_type}\n"
        f"📐 Площадь: {area} кв.м.\n"
        f"🛠 Изменения: {changes}"
    )
    
    from config import ADMIN_ID
    try:
        await message.bot.send_message(ADMIN_ID, report, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to send invest report to admin: {e}")

    await message.answer(
        "✅ Данные приняты. Специалист компании GEORIS свяжется с вами в ближайшее время для уточнения деталей и консультации.",
        parse_mode="HTML"
    )
    await state.clear()


def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков инвест-режима"""
    dp.include_router(router)
