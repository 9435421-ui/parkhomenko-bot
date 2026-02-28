"""
Обработчик диалогового режима консультаций
"""
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

dialog_router = Router()


@dialog_router.message()
async def dialog_handler(message: Message, state: FSMContext):
    """
    Обработчик диалогового режима консультаций
    TODO: Реализовать логику диалога с ИИ-консультантом
    """
    await message.answer("Диалоговый режим в разработке. Используйте /start для начала работы.")


# Экспорт router для совместимости с handlers/__init__.py
router = dialog_router
