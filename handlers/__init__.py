"""
Обработчики команд и сообщений (aiogram).
"""
from .start import router as start_router
from .quiz import router as quiz_router
from .dialog import router as dialog_router
from .content import content_router
from .admin import admin_router
from .vk_publisher import VKPublisher
from .max_uploader import MaxUploader

__all__ = ['start_router', 'quiz_router', 'dialog_router', 'content_router', 'admin_router', 'VKPublisher', 'MaxUploader']
