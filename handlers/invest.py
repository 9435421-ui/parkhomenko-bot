"""
Обработчик инвест-калькулятора
"""
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

router = Router()


@router.message()
async def invest_handler(message: Message, state: FSMContext):
    """
    Обработчик инвест-калькулятора
    TODO: Реализовать логику расчета инвестиционного потенциала
    """
    await message.answer("Инвест-калькулятор в разработке. Используйте /start для начала работы.")
