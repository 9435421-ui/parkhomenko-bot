#!/usr/bin/env python3
import os, sys, asyncio, logging
sys.path.insert(0, '/root/PARKHOMENKO_BOT')
from dotenv import load_dotenv
load_dotenv('/root/PARKHOMENKO_BOT/.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from config import CHANNEL_ID_GEORIS, CHANNEL_ID_DOM_GRAD
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.scheduler_ref import set_scheduler

async def publish_scheduled_posts(bot):
    """Проверяет БД и публикует посты у которых время пришло"""
    from datetime import datetime
    from database.db import db
    from services.publisher import publisher
    from handlers.content_bot import ensure_quiz_and_hashtags, download_photo
    
    if not publisher.bot:
        publisher.bot = bot
    
    now = datetime.now()
    # Получаем все посты со статусом approved и датой <= now
    async with db.conn.cursor() as cursor:
        await cursor.execute(
            "SELECT id, title, body, image_url FROM content_plan WHERE status='approved' AND publish_date <= ? AND publish_date IS NOT NULL",
            (now.strftime("%Y-%m-%d %H:%M:%S"),)
        )
        posts = await cursor.fetchall()
    
    for post in posts:
        post_id, title, body, image_url = post[0], post[1], post[2], post[3]
        try:
            text = ensure_quiz_and_hashtags(body)
            image_bytes = None
            if image_url:
                image_bytes = await download_photo(bot, image_url)
            
            # Публикуем в TG
            await publisher.publish_to_telegram(CHANNEL_ID_GEORIS, text, image_bytes)
            await publisher.publish_to_telegram(CHANNEL_ID_DOM_GRAD, text, image_bytes)
            
            # Публикуем в VK
            if image_bytes:
                await publisher.vk.post_with_photo(text, image_bytes)
            else:
                await publisher.vk.post_text_only(text)
            
            # Отмечаем как опубликованный
            await db.update_content_post(post_id, status="published")
            
            logger.info(f"✅ Автопубликация поста #{post_id}: {title}")
        except Exception as e:
            logger.error(f"❌ Ошибка автопубликации поста #{post_id}: {e}")

async def main():
    from aiogram import Bot, Dispatcher
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.client.default import DefaultBotProperties
    from config import CONTENT_BOT_TOKEN
    from handlers.content_bot import content_router
    from handlers.video_report_handler import router as video_router
    from database.db import db
    from utils.bot_config import set_content_bot

    await db.connect()
    bot = Bot(token=CONTENT_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    set_content_bot(bot)

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(content_router)
    dp.include_router(video_router)

    me = await bot.get_me()
    logger.info(f"🚀 Контент-бот: @{me.username}")

    # Запускаем планировщик автопубликации
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(publish_scheduled_posts, 'interval', minutes=1, args=[bot])
    scheduler.start()
    set_scheduler(scheduler)
    logger.info("✅ Планировщик автопубликации запущен")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
