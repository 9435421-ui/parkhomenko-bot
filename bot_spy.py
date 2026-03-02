"""
Бот шпиона - поиск лидов в ВК и Telegram
aiogram 3.x версия
"""
import logging
import os
import signal
import sys
import asyncio
from pathlib import Path
from datetime import datetime

try:
    from aiogram import Bot, Dispatcher
    try:
        # aiogram 3.x
        from aiogram.fsm.storage.memory import MemoryStorage
        from aiogram.client.default import DefaultBotProperties
        AIOGRAM_VERSION = 3
    except ImportError:
        # aiogram 2.x
        from aiogram.contrib.fsm_storage.memory import MemoryStorage
        AIOGRAM_VERSION = 2
except ImportError:
    logger.error("❌ aiogram не установлен")
    sys.exit(1)

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, LEADS_GROUP_CHAT_ID
from services.lead_hunter import LeadHunter
from services.lead_hunter.discovery import Discovery
from services.scout_parser import scout_parser
from hunter_standalone.database import HunterDatabase
from hunter_standalone import LeadHunter as StandaloneLeadHunter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

LOCK_FILE = Path(__file__).resolve().parent / "bot_spy.lock"


def _acquire_lock():
    if LOCK_FILE.exists():
        try:
            raw = LOCK_FILE.read_text().strip()
            old_pid = int(raw)
        except (ValueError, OSError):
            old_pid = None
        if old_pid and old_pid != os.getpid():
            try:
                os.kill(old_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            LOCK_FILE.unlink()
        except OSError:
            pass
    LOCK_FILE.write_text(str(os.getpid()))


def _release_lock():
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
    except OSError:
        pass


async def clear_webhook(bot: Bot):
    """Очистка webhook перед запуском polling"""
    try:
        webhook_info = await bot.get_webhook_info()
        if hasattr(webhook_info, 'url') and webhook_info.url:
            logger.info(f"⚠️ Очистка webhook: {webhook_info.url}")
            await bot.delete_webhook()
            logger.info("✅ Webhook очищен")
        else:
            logger.info("ℹ️ Webhook не был установлен")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при очистке webhook: {e}")


async def start_spy_bot():
    """Запуск бота шпиона (поиск лидов в ВК и Telegram)"""
    logger.info("🚀 Запуск бота шпиона...")
    _acquire_lock()

    # Создаем бота шпиона
    if AIOGRAM_VERSION == 3:
        spy_bot = Bot(token=BOT_TOKEN or "", default=DefaultBotProperties(parse_mode="HTML"))
        storage = MemoryStorage()
        dp_spy = Dispatcher(storage=storage)
    else:
        spy_bot = Bot(token=BOT_TOKEN or "", parse_mode="HTML")
        storage = MemoryStorage()
        dp_spy = Dispatcher(spy_bot, storage=storage)

    # Очистка webhook
    await clear_webhook(spy_bot)

    # Инициализация LeadHunter
    hunter = LeadHunter()
    discovery = Discovery()
    parser = scout_parser

    # Инициализация планировщика
    scheduler = AsyncIOScheduler()
    scheduler.add_job(hunter.hunt, 'interval', minutes=30)
    scheduler.add_job(discovery.find_new_sources, 'interval', hours=6)

    scheduler.start()
    logger.info("✅ Планировщик запущен")

    # Принудительный запуск LeadHunter
    logger.info("🏹 LeadHunter: принудительный запуск первого цикла...")
    asyncio.create_task(hunter.hunt())

    # Запускаем polling для бота шпиона
    await dp_spy.start_polling(spy_bot, skip_updates=True)

    # Очистка при завершении
    scheduler.shutdown()
    _release_lock()


if __name__ == "__main__":
    try:
        asyncio.run(start_spy_bot())
    except KeyboardInterrupt:
        logger.info("🛑 Бот шпиона остановлен")
        sys.exit(0)