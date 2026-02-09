"""
Основной бот ТЕРИОН - aiogram 3.x + Content Factory.
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

from config import BOT_TOKEN, GROUP_ID, THREAD_ID_LEADS, CHANNEL_ID
from handlers import start_router, quiz_router, content_router, dialog_router, admin_router
from database import db
from utils import kb, router_ai
from agents.viral_hooks_agent import viral_hooks_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальный экземпляр бота
bot: Bot = None
dp: Dispatcher = None
scheduler: AsyncIOScheduler = None


async def on_startup():
    """Инициализация при запуске"""
    global bot, dp, scheduler
    
    # Подключаем БД
    await db.connect()
    
    # Индексируем базу знаний
    await kb.index_documents()
    
    # Тест ViralHooksAgent
    logger.info("🧪 Тест ViralHooksAgent...")
    try:
        hooks = await viral_hooks_agent.generate_hooks("Ипотека 2026", count=5)
        logger.info(f"📝 ViralHooksAgent result: {len(hooks)} hooks generated")
        for i, hook in enumerate(hooks, 1):
            logger.info(f"  {i}. {hook['text']}")
    except Exception as e:
        logger.error(f"❌ ViralHooksAgent error: {e}")
    
    # Запускаем планировщик
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_scheduled_posts, 'cron', hour=12, minute=0, timezone='Europe/Moscow')
    scheduler.start()
    logger.info("⏰ APScheduler запущен (12:00 МСК)")
    
    print("✅ Бот ТЕРИОН готов!")
    print(f"📚 База знаний: {len(kb.documents)} документов")
    print(f"🧠 Router AI: {'подключен' if router_ai.api_key else 'не настроен'}")
    print(f"📤 Группа: {GROUP_ID} (thread: {THREAD_ID_LEADS})")


async def check_scheduled_posts():
    """Проверка и публикация запланированных постов (12:00 МСК)"""
    logger.info("⏰ Проверка запланированных постов...")
    # TODO: реализовать логику публикации


async def main():
    """Запуск бота"""
    global bot, dp
    
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    dp = Dispatcher(storage=MemoryStorage())

    # ⚠️ ВАЖНО: Порядок роутеров!
    # 1. start - /start и приветствие
    # 2. quiz - квиз (FSM, должен обрабатывать до dialog)
    # 3. content - создание постов
    # 4. dialog - YandexGPT (только когда не в квизе!)
    # 5. admin - админка
    dp.include_router(start_router)
    dp.include_router(quiz_router)
    dp.include_router(content_router)
    dp.include_router(dialog_router)
    dp.include_router(admin_router)

    await on_startup()
    
    print("🚀 Запуск поллинга...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
