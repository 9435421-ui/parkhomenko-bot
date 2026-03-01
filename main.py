"""
Основной бот ТЕРИОН - aiogram 2.x + Content Factory.
aiogram 2.x версия для совместимости с vkbottle
"""
import logging
import os
import signal
import sys
import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, CONTENT_BOT_TOKEN, LEADS_GROUP_CHAT_ID
from handlers import register_all_handlers
from database import db
from utils import kb
from agents.creative_agent import creative_agent
from services.lead_hunter import LeadHunter
from services.publisher import AutoPoster

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

LOCK_FILE = Path(__file__).resolve().parent / "bot.lock"


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


main_bot = None
content_bot = None
scheduler = None


async def check_and_publish_scheduled_posts():
    try:
        posts = await db.get_posts_to_publish()
        if not posts:
            logger.info("No posts to publish")
            return
        
        for post in posts:
            try:
                title = (post.get("title") or "").strip()
                body = (post.get("body") or "").strip()
                text = f"<b>{title}</b>\n\n{body}" if title else body
                
                from services.publisher import publisher as pub_instance
                if pub_instance:
                    await pub_instance.publish_all(text, None)
                
                await db.mark_as_published(post["id"])
            except Exception as e:
                logger.error("Error publishing post #%s: %s", post.get("id"), e)
    except Exception as e:
        logger.error("Error in check_and_publish: %s", e)


async def on_startup_main(dp):
    global scheduler
    logger.info("Starting main bot (Anton)...")
    
    await db.connect()
    await kb.index_documents()
    register_all_handlers(dp)
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_and_publish_scheduled_posts, "interval", hours=1)
    
    hunter = LeadHunter()
    scheduler.add_job(hunter.hunt, 'interval', minutes=5)
    scheduler.add_job(creative_agent.scout_topics, 'interval', hours=6)
    
    scheduler.start()
    logger.info("Scheduler started")


async def on_shutdown_main(dp):
    logger.info("Stopping main bot...")
    if scheduler:
        scheduler.shutdown()
    _release_lock()


async def on_startup_content(dp):
    logger.info("Starting content bot...")


async def on_shutdown_content(dp):
    logger.info("Stopping content bot...")


def main():
    global main_bot, content_bot
    
    _acquire_lock()
    
    main_bot = Bot(token=BOT_TOKEN or "", parse_mode="HTML")
    content_bot = Bot(token=CONTENT_BOT_TOKEN or "", parse_mode="HTML")
    
    from utils.bot_config import set_main_bot
    set_main_bot(main_bot)
    
    from services import publisher
    publisher.publisher = AutoPoster(content_bot)
    
    storage = MemoryStorage()
    dp_main = Dispatcher(main_bot, storage=storage)
    dp_content = Dispatcher(content_bot, storage=storage)
    
    dp_main.register_startup_hook(on_startup_main)
    dp_main.register_shutdown_hook(on_shutdown_main)
    dp_content.register_startup_hook(on_startup_content)
    dp_content.register_shutdown_hook(on_shutdown_content)
    
    executor.start_polling(dp_main, skip_updates=True)


if __name__ == "__main__":
    main()
