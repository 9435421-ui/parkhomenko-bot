"""
Обработчики команд и сообщений
"""
from .start import router as start_router
from .quiz import router as router
from .dialog import router as dialog_router
from .invest import router as invest_router

__all__ = ['start_router', 'router', 'dialog_router', 'invest_router']
