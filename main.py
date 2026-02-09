"""
Основной бот ТЕРИОН - aiogram 3.x + Content Factory.
Запуск ДВУХ ботов: main_bot + content_bot
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime

from config import BOT_TOKEN, CONTENT_BOT_TOKEN, GROUP_ID, THREAD_ID_LEADS, CHANNEL_ID
from handlers import start_router, quiz_router, content_router, dialog_router, admin_router
from database import db
from utils import kb, router_ai
from agents.viral_hooks_agent import viral_hooks_agent
from agents.scout_agent import scout_agent

# Настройка логов — видим ВСЕ события!
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Глобальные экземпляры
main_bot: Bot = None
content_bot: Bot = None
dp: Dispatcher = None


async def on_startup():
    """Инициализация при запуске"""
    global main_bot, content_bot, dp
    
    # Подключаем БД
    await db.connect()
    
    # Индексируем базу знаний
    await kb.index_documents()
    
    # Тесты агентов — НЕблокирующие
    asyncio.create_task(test_agents_background())
    
    # Запускаем планировщик
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_birthdays_and_holidays, 'cron', hour=9, minute=0, timezone='Europe/Moscow')
    scheduler.add_job(check_scheduled_posts, 'cron', hour=12, minute=0, timezone='Europe/Moscow')
    scheduler.start()
    
    logger.info("=" * 50)
    logger.info("✅ Бот ТЕРИОН готов!")
    logger.info(f"📚 База знаний: {len(kb.documents)} документов")
    logger.info(f"🧠 Router AI: {'подключен' if router_ai.api_key else 'не настроен'}")
    logger.info(f"📤 Группа: {GROUP_ID}")
    logger.info("=" * 50)


async def test_agents_background():
    """Тесты агентов в фоне"""
    logger.info("🧪 Тесты агентов (фоновый режим)...")
    
    try:
        hooks = await viral_hooks_agent.generate_hooks("перепланировка", count=3)
        logger.info(f"📝 ViralHooksAgent: {len(hooks)} hooks OK")
    except Exception as e:
        logger.warning(f"⚠️ ViralHooksAgent: {e}")
    
    try:
        topics = await scout_agent.scout_topics(count=1)
        logger.info(f"📌 ScoutAgent: {len(topics)} topics OK")
    except Exception as e:
        logger.warning(f"⚠️ ScoutAgent: {e}")


async def check_scheduled_posts():
    """Проверка и публикация постов (12:00 МСК)"""
    logger.info("⏰ Проверка запланированных постов...")


async def check_birthdays_and_holidays():
    """Проверка дней рождения (09:00 МСК)"""
    logger.info("🎂 Проверка дней рождения...")
    
    try:
        birthdays = await db.get_today_birthdays()
        if birthdays:
            for client in birthdays:
                logger.info(f"🎂 ДР сегодня: {client.get('name')}")
        else:
            logger.info("📭 Дней рождения сегодня нет")
    except Exception as e:
        logger.error(f"❌ Ошибка ДР: {e}")


async def main():
    """Запуск ДВУХ ботов через asyncio.gather"""
    global main_bot, content_bot, dp
    
    # === BOT 1: Основной бот (консультант) ===
    main_bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    
    # === BOT 2: Content бот (посты) ===
    content_bot = Bot(
        token=CONTENT_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    
    # === ОДИН Dispatcher для обоих ботов ===
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрируем роутеры
    dp.include_router(start_router)
    dp.include_router(quiz_router)
    dp.include_router(content_router)
    dp.include_router(dialog_router)
    dp.include_router(admin_router)
    
    await on_startup()
    
    logger.info("🚀 Запуск двух ботов...")
    logger.info(f"📱 main_bot: {BOT_TOKEN[:10]}...")
    logger.info(f"📱 content_bot: {CONTENT_BOT_TOKEN[:10]}...")
    
    # === ЗАПУСК ОБОИХ БОТОВ ===
    try:
        await asyncio.gather(
            dp.start_polling(main_bot),
            dp.start_polling(content_bot)
        )
    except Exception as e:
        logger.error(f"❌ Ошибка поллинга: {e}")


if __name__ == "__main__":
    asyncio.run(main())
