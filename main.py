"""
Основной бот ТЕРИОН - aiogram 3.x + Content Factory.
Запуск ДВУХ ботов с РАЗДЕЛЬНЫМИ Dispatchers:
- main_bot (АНТОН): консультант по перепланировкам
- content_bot (ДОМ ГРАНД): контент и посты
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, CONTENT_BOT_TOKEN
from handlers.main_bot import start_router, quiz_router, dialog_router
from handlers import content_router, admin_router
from database import db
from utils import kb
from middleware.logging import UnhandledCallbackMiddleware

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def main():
    logger.info("🎯 Запуск ЭКОСИСТЕМЫ TERION...")
    
    # 1. Единая инициализация ресурсов
    await db.connect()
    await kb.index_documents()
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(lambda: logger.info("⏰ Проверка постов"), 'cron', hour=12)
    scheduler.start()
    
    # 2. Настройка АНТОНА
    main_bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp_main = Dispatcher(storage=MemoryStorage())
    dp_main.callback_query.middleware(UnhandledCallbackMiddleware())
    dp_main.include_routers(start_router, quiz_router, dialog_router)
    
    # 3. Настройка ДОМ ГРАНД
    content_bot = Bot(token=CONTENT_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp_content = Dispatcher(storage=MemoryStorage())
    dp_content.callback_query.middleware(UnhandledCallbackMiddleware())
    dp_content.include_routers(content_router, admin_router)
    
    # 4. Параллельный запуск
    await asyncio.gather(
        dp_main.start_polling(main_bot),
        dp_content.start_polling(content_bot)
    )


if __name__ == "__main__":
    asyncio.run(main())
