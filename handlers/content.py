"""
Обработчик контент-генерации
aiogram 3.x версия
"""
from aiogram import Router, Dispatcher

router = Router()


def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков контент-генерации"""
    dp.include_router(router)
