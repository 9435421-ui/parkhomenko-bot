"""
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

content_bot_instance = None

def set_content_bot(bot):
    global content_bot_instance
    content_bot_instance = bot
    logger.info("✅ Контент-бот установлен в bot_config")

def get_content_bot():
    return content_bot_instance
