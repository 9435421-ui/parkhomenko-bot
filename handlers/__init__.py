"""
Обработчики команд и сообщений (aiogram).
"""
from .start import router as start_router
from .quiz import router as quiz_router
from .dialog import router as dialog_router
from .content import router as content_router
from .admin import router as admin_router

__all__ = ['start_router', 'quiz_router', 'dialog_router', 'content_router', 'admin_router']
