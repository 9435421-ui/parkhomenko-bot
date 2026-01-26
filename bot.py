"""
Главный файл бота «Лад в квартире»
ИИ-консультант Антон - помощник эксперта Пархоменко Юлии Владимировны
"""
import asyncio
import logging
import sys
from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv

# Импорт модулей проекта
from database import db
from utils import kb
from handlers import start_router, quiz_router, dialog_router, invest_router

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    """Действия при запуске бота"""
    logger.info("🚀 Запуск бота «Лад в квартире»...")
    
    # Подключение к базе данных
    await db.connect()
    logger.info("✅ База данных подключена")
    
    # Индексация базы знаний
    doc_count = await kb.index_documents()
    logger.info(f"✅ База знаний проиндексирована: {doc_count} документов")
    
    # Получение информации о боте
    bot_info = await bot.get_me()
    logger.info(f"✅ Бот запущен: @{bot_info.username}")
    logger.info(f"📋 Имя бота: {bot_info.first_name}")
    
    # Список категорий документов
    categories = kb.get_document_categories()
    logger.info(f"📚 Категории документов: {', '.join(categories)}")


async def on_shutdown(bot: Bot):
    """Действия при остановке бота"""
    logger.info("🛑 Остановка бота...")
    
    # Закрытие соединени с БД
    await db.close()
    logger.info("✅ База данных отключена")
    
    logger.info("👋 Бот остановлен")


async def main():
    """Основная функция запуска бота"""
    
    # Получение токена из переменных окружения
    token = getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("❌ TELEGRAM_TOKEN не установлен в .env файле!")
        sys.exit(1)
    
    # Инициализация бота и диспетчера
    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher()
    
    # Регистрация роутеров (порядок важен!)
    dp.include_router(start_router)
    dp.include_router(quiz_router)
    dp.include_router(dialog_router)
    dp.include_router(invest_router)
    
    # Регистрация событий запуска и остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Запуск бота
    try:
        logger.info("⏳ Запуск polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    """Точка входа в приложение"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚡ Бот остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logger.error(f"💥 Неожиданная ошибка: {e}", exc_info=True)
        sys.exit(1)
