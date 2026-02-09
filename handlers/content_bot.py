"""
Обработчики для бота ДОМ ГРАНД (контент).
"""
from .content import router as content_router
from .admin import router as admin_router

__all__ = ['content_router', 'admin_router']
