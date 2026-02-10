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
from aiogram import BaseMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# === Middleware для логирования необработанных callback ===
class UnhandledCallbackMiddleware(BaseMiddleware):
    """Логирует все callback, которые не были обработаны"""
    
    async def __call__(self, handler, event, data):
        try:
            response = await handler(event, data)
            return response
        except Exception as e:
            # Логируем необработанные callback
            if hasattr(event, 'callback_query'):
                cb = event.callback_query
                logger.warning(f"🔔 Unhandled callback: {cb.data} от @{cb.from_user.username}")
            raise

from config import BOT_TOKEN, CONTENT_BOT_TOKEN, LEADS_GROUP_CHAT_ID, THREAD_ID_KVARTIRY, THREAD_ID_KOMMERCIA, THREAD_ID_DOMA
from handlers.main_bot import start_router, quiz_router, dialog_router
from handlers import content_router
from handlers import admin_router
from database import db
from utils import kb, router_ai
from agents.viral_hooks_agent import viral_hooks_agent
from agents.scout_agent import scout_agent

# DEBUG логи — видим ВСЕ события!
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def on_startup_all():
    """Общая инициализация"""
    await db.connect()
    await kb.index_documents()
    asyncio.create_task(test_agents_background())
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_birthdays, 'cron', hour=9, minute=0, timezone='Europe/Moscow')
    scheduler.add_job(check_posts, 'cron', hour=12, minute=0, timezone='Europe/Moscow')
    scheduler.start()
    
    logger.info("=" * 50)
    logger.info("✅ ТЕРИОН готов!")
    logger.info(f"📚 База: {len(kb.documents)} документов")
    logger.info("=" * 50)


async def test_agents_background():
    """Тесты агентов в фоне"""
    try:
        hooks = await viral_hooks_agent.generate_hooks("перепланировка", count=3)
        logger.info(f"📝 ViralHooks: {len(hooks)} OK")
    except Exception as e:
        logger.warning(f"⚠️ ViralHooks: {e}")
    
    try:
        topics = await scout_agent.scout_topics(count=1)
        logger.info(f"📌 Scout: {len(topics)} OK")
    except Exception as e:
        logger.warning(f"⚠️ Scout: {e}")


async def check_posts():
    logger.info("⏰ 12:00 — проверка постов")


async def check_birthdays():
    logger.info("🎂 09:00 — проверка ДР")
    try:
        birthdays = await db.get_today_birthdays()
        for b in birthdays:
            logger.info(f"🎂 ДР: {b.get('name')}")
    except Exception as e:
        logger.error(f"❌ ДР ошибка: {e}")


async def run_main_bot():
    """Запуск АНТОНА (консультант)"""
    logger.info("🚀 Запуск main_bot (АНТОН)...")
    
    main_bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp_main = Dispatcher(storage=MemoryStorage())
    
    # Middleware для логирования
    dp_main.message.middleware(UnhandledCallbackMiddleware())
    dp_main.callback_query.middleware(UnhandledCallbackMiddleware())
    
    # Роутеры АНТОНА
    dp_main.include_router(start_router)
    dp_main.include_router(quiz_router)
    dp_main.include_router(dialog_router)
    
    await on_startup_all()
    
    logger.info("📱 main_bot (АНТОН) слушает...")
    await dp_main.start_polling(main_bot)


async def run_content_bot():
    """Запуск ДОМ ГРАНДА (контент)"""
    logger.info("🚀 Запуск content_bot (ДОМ ГРАНД)...")
    
    content_bot = Bot(token=CONTENT_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp_content = Dispatcher(storage=MemoryStorage())
    
    # Middleware для логирования
    dp_content.message.middleware(UnhandledCallbackMiddleware())
    dp_content.callback_query.middleware(UnhandledCallbackMiddleware())
    
    # Роутеры ДОМ ГРАНДА
    dp_content.include_router(content_router)
    dp_content.include_router(admin_router)
    
    # Общая инициализация (без дублирования БД)
    await kb.index_documents()
    asyncio.create_task(test_agents_background())
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_birthdays, 'cron', hour=9, minute=0, timezone='Europe/Moscow')
    scheduler.add_job(check_posts, 'cron', hour=12, minute=0, timezone='Europe/Moscow')
    scheduler.start()
    
    logger.info("📱 content_bot (ДОМ ГРАНД) слушает...")
    await dp_content.start_polling(content_bot)


async def main():
    """ОДНОВРЕМЕННЫЙ запуск двух ботов"""
    logger.info("=" * 50)
    logger.info("🎯 Запуск СИСТЕМЫ...")
    logger.info("=" * 50)
    
    try:
        await asyncio.gather(
            run_main_bot(),
            run_content_bot()
        )
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(main())
