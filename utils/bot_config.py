"""
<<<<<<< HEAD
bot_config - единый источник истины для экземпляра основного бота
Позволяет другим модулям получать доступ к боту без создания новых экземпляров
"""
import logging

logger = logging.getLogger(__name__)

# Глобальная переменная для хранения экземпляра основного бота
main_bot_instance = None


def set_main_bot(bot):
    """
    Устанавливает глобальный экземпляр основного бота
    
    Args:
        bot: Экземпляр aiogram.Bot
    """
    global main_bot_instance
    main_bot_instance = bot
    logger.info("✅ Основной бот установлен в bot_config")


def get_main_bot():
    """
    Возвращает глобальный экземпляр основного бота
    
    Returns:
        Экземпляр aiogram.Bot или None, если бот еще не установлен
    """
    return main_bot_instance
=======
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
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
