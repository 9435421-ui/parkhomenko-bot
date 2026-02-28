"""
Обработчики команд и сообщений
"""
from .start import router as start_router
from .quiz import quiz_router
from .dialog import dialog_router
from .invest import router as invest_router
from .admin import router as admin_router

# Импорт content_router и creator_router (если файлы существуют)
try:
    from .content import router as content_router
except ImportError:
    content_router = None

try:
    from .creator import creator_router
except ImportError:
    creator_router = None

__all__ = ['start_router', 'quiz_router', 'dialog_router', 'invest_router', 'admin_router', 'content_router', 'creator_router']
