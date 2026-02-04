import asyncio
import logging
import sys
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

# Добавляем корень проекта в путь поиска модулей для корректных импортов
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from config import BOT_TOKEN
from handlers import start_router, quiz_router, dialog_router, invest_router, admin_router
from database.db import db
from services.loyalty_service import LoyaltyService

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("main_bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def main():
    if not BOT_TOKEN:
        logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не найден в .env")
        return

    # Инициализация базы данных
    try:
        await db.connect()
        logger.info("✅ База данных подключена")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к БД: {e}")
        return

    # Инициализация бота с использованием современного синтаксиса aiogram 3.7+
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )

    dp = Dispatcher(storage=MemoryStorage())

    # Инициализация сервисов лояльности
    loyalty = LoyaltyService(bot)
    asyncio.create_task(loyalty.run_daily_check(db))

    # Регистрация роутеров
    dp.include_router(admin_router)
    dp.include_router(start_router)
    dp.include_router(quiz_router)
    dp.include_router(invest_router)
    dp.include_router(dialog_router)

    logger.info("🚀 Бот «ТЕРИОН» успешно запущен и начинает опрос обновлений...")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка во время работы бота: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Бот остановлен пользователем")
