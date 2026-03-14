"""
Обработчики для главного бота АНТОН (консультант по перепланировкам).
"""
from .start import router as start_router
from .quiz import router as quiz_router
from .dialog import router as dialog_router

__all__ = ['start_router', 'quiz_router', 'dialog_router']
