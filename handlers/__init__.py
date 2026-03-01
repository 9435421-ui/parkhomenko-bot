"""
Обработчики команд и сообщений
aiogram 2.x версия
"""
from aiogram import Dispatcher


def register_all_handlers(dp: Dispatcher):
    """Регистрация всех обработчиков для aiogram 2.x"""
    from .start import register_handlers as register_start
    from .quiz import register_handlers as register_quiz
    from .dialog import register_handlers as register_dialog
    from .invest import register_handlers as register_invest
    from .admin import register_handlers as register_admin
    
    register_start(dp)
    register_quiz(dp)
    register_dialog(dp)
    register_invest(dp)
    register_admin(dp)
    
    # Регистрация content и creator если есть
    try:
        from .content import register_handlers as register_content
        register_content(dp)
    except ImportError:
        pass
    
    try:
        from .creator import register_handlers as register_creator
        register_creator(dp)
    except ImportError:
        pass


# Для обратной совместимости
start_router = None
quiz_router = None
dialog_router = None
invest_router = None
admin_router = None
content_router = None
creator_router = None

__all__ = ['register_all_handlers', 'start_router', 'quiz_router', 'dialog_router', 
           'invest_router', 'admin_router', 'content_router', 'creator_router']
