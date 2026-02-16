"""
Общий экземпляр бота для отправки сообщений из сервисов (LeadHunter, отчёты и т.д.).
Устанавливается в main.py после создания ботов. Избегает создания множества Bot(token=...)
и риска конфликтов getUpdates / TelegramConflictError.
"""
from typing import Optional
from aiogram import Bot

_main_bot: Optional[Bot] = None


def set_main_bot(bot: Bot) -> None:
    """Установить экземпляр основного бота (вызывается из main.py)."""
    global _main_bot
    _main_bot = bot


def get_main_bot() -> Optional[Bot]:
    """Получить общий экземпляр основного бота. None до вызова set_main_bot из main.py."""
    return _main_bot
