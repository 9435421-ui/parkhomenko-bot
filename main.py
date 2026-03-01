"""
Основной бот ТЕРИОН - aiogram 3.x + Content Factory.
Запуск ДВУХ ботов с РАЗДЕЛЬНЫМИ Dispatchers:
- main_bot (АНТОН): консультант по перепланировкам
- content_bot (ДОМ ГРАНД): контент и посты

aiogram 3.x версия для Python 3.12
"""
import logging
import os
import signal
import sys
import asyncio
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
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


async def main():
    _acquire_lock()
    
    logger.info("🚀 Переход на Aiogram 3.x выполнен. Конфликт Python 3.12 исчерпан.")
    logger.info("🎯 Запуск ЭКОСИСТЕМЫ TERION...")
    
    # Создаем ботов
    main_bot = Bot(token=BOT_TOKEN or "", default=DefaultBotProperties(parse_mode="HTML"))
    content_bot = Bot(token=CONTENT_BOT_TOKEN or "", default=DefaultBotProperties(parse_mode="HTML"))
    
    # Сохраняем main_bot для использования в других модулях
    from utils.bot_config import set_main_bot
    set_main_bot(main_bot)
    
    # Инициализация publisher
    from services import publisher
    publisher.publisher = AutoPoster(content_bot)
    
    # Создаем диспетчеры
    storage = MemoryStorage()
    dp_main = Dispatcher(storage=storage)
    dp_content = Dispatcher(storage=storage)
    
    # Регистрация обработчиков
    register_all_handlers(dp_main)
    
    # Инициализация ресурсов
    await db.connect()
    await kb.index_documents()
    
    # Проверка YandexGPT
    logger.info("🧠 Проверка YandexGPT...")
    try:
        from config import YANDEX_API_KEY, FOLDER_ID
        if YANDEX_API_KEY and FOLDER_ID:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
                headers = {
                    "Authorization": f"Api-Key {YANDEX_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "modelUri": f"gpt://{FOLDER_ID}/yandexgpt-lite",
                    "completionOptions": {"temperature": 0.3, "maxTokens": 10},
                    "messages": [{"role": "user", "text": "Тест"}]
                }
                async with session.post(url, headers=headers, json=payload, timeout=10) as resp:
                    if resp.status == 200:
                        logger.info("✅ YandexGPT: подключение успешно")
                    else:
                        logger.warning(f"⚠️ YandexGPT: ошибка HTTP {resp.status}")
        else:
            logger.warning("⚠️ YANDEX_API_KEY или FOLDER_ID не настроены")
    except Exception as e:
        logger.warning(f"⚠️ YandexGPT не отвечает, лиды будут сырыми")
    
    # Инициализация планировщика
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_and_publish_scheduled_posts, "interval", hours=1)
    
    hunter = LeadHunter()
    scheduler.add_job(hunter.hunt, 'interval', minutes=30)
    scheduler.add_job(creative_agent.scout_topics, 'interval', hours=6)
    
    scheduler.start()
    logger.info("✅ Планировщик запущен")
    
    # Принудительный запуск LeadHunter сразу после старта
    logger.info("🏹 LeadHunter: принудительный запуск первого цикла...")
    asyncio.create_task(hunter.hunt())
    
    # Запускаем polling
    await dp_main.start_polling(main_bot, skip_updates=True)
    
    # Очистка при завершении
    scheduler.shutdown()
    _release_lock()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен")
        sys.exit(0)
