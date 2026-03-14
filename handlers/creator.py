"""
Обработчик для создателя контента
aiogram 3.x версия
"""
from aiogram import Router, Dispatcher

creator_router = Router()


def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков создателя контента"""
    dp.include_router(creator_router)
