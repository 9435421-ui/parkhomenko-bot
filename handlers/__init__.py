"""
<<<<<<< HEAD
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
=======
Обработчики команд и сообщений (aiogram).
"""
from .start import router as start_router
from .quiz import router as quiz_router
from .dialog import router as dialog_router
from .content import content_router
from .admin import router as admin_router
from .vk_publisher import VKPublisher
from .max_uploader import MaxUploader

__all__ = ['start_router', 'quiz_router', 'dialog_router', 'content_router', 'admin_router', 'VKPublisher', 'MaxUploader']
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
