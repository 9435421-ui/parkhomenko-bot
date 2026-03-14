"""
Обработчики команд и сообщений
aiogram 3.x версия
"""
from aiogram import Dispatcher
from .content import content_router
from .creator import creator_router
from .start import start_router
from .admin import admin_router

__all__ = ["register_all_handlers", "content_router", "creator_router", "start_router", "admin_router"]


def register_all_handlers(dp: Dispatcher):
    """Регистрация всех обработчиков для aiogram 3.x"""
    from .start import register_handlers as register_start
    from .quiz import register_handlers as register_quiz
    from .dialog import register_handlers as register_dialog
    from .invest import register_handlers as register_invest
    from .admin import register_handlers as register_admin
    from .content import register_handlers as register_content
    from .creator import register_handlers as register_creator
    
    register_start(dp)
    register_quiz(dp)
    register_dialog(dp)
    register_invest(dp)
    register_admin(dp)
    register_content(dp)
    register_creator(dp)
