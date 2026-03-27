import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Инициализация логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Импортируем конфиги
try:
    from config import CHANNEL_ID_GEORIS, CHANNEL_ID_DOM_GRAD, CONTENT_BOT_TOKEN
except ImportError:
    logger.error("❌ Не удалось загрузить config")
    CHANNEL_ID_GEORIS = 0
    CHANNEL_ID_DOM_GRAD = 0
    CONTENT_BOT_TOKEN = ""


async def publish_scheduled_posts(bot):
    """
    ИСПРАВЛЕННАЯ ФУНКЦИЯ: публикует посты в Telegram, затем в VK.
    
    КЛЮЧЕВЫЕ ИЗМЕНЕНИЯ:
    1. TG публикация обязательна, VK опциональна
    2. Пост отмечается как 'published' сразу после TG, даже если VK упадёт
    3. Используется правильный метод publisher.publish_to_vk() вместо publisher.vk.*
    4. Исключения в VK НЕ рвут цикл
    """
    from database.db import db
    from services.publisher import publisher
    from handlers.content_bot import ensure_quiz_and_hashtags, download_photo

    if not publisher.bot:
        publisher.bot = bot

    now = datetime.now()
    
    # Получаем все посты со статусом 'approved' и датой <= now
    async with db.conn.cursor() as cursor:
        await cursor.execute(
            "SELECT id, title, body, image_url FROM content_plan "
            "WHERE status='approved' AND publish_date <= ? AND publish_date IS NOT NULL",
            (now.strftime("%Y-%m-%d %H:%M:%S"),)
        )
        posts = await cursor.fetchall()

    if not posts:
        return  # Нет постов для публикации
    
    logger.info(f"📋 Найдено {len(posts)} постов для автопубликации")

    for post in posts:
        post_id, title, body, image_url = post[0], post[1], post[2], post[3]
        
        try:
            # === ПОДГОТОВКА КОНТЕНТА ===
            text = ensure_quiz_and_hashtags(body)
            image_bytes = None
            
            if image_url:
                try:
                    image_bytes = await download_photo(bot, image_url)
                except Exception as img_err:
                    logger.warning(f"⚠️ Не удалось загрузить фото для #{post_id}: {img_err}")
                    image_bytes = None
            
            # === TELEGRAM ПУБЛИКАЦИЯ (ОБЯЗАТЕЛЬНАЯ) ===
            tg_success = False
            try:
                await publisher.publish_to_telegram(CHANNEL_ID_GEORIS, text, image_bytes)
                await publisher.publish_to_telegram(CHANNEL_ID_DOM_GRAD, text, image_bytes)
                tg_success = True
                logger.info(f"✅ TG публикация #{post_id}: {title}")
            except Exception as tg_err:
                logger.error(f"❌ ОШИБКА TG публикации #{post_id}: {tg_err}")
                # Пропускаем этот пост если TG не работает
                continue
            
            # === ОБНОВЛЕНИЕ БД (СРАЗУ ПОСЛЕ TG, НЕ ДОЖИДАЯСЬ VK) ===
            try:
                await db.update_content_post(post_id, status="published")
                logger.info(f"✅ Пост #{post_id} отмечен как опубликованный в БД")
            except Exception as db_err:
                logger.error(f"❌ ОШИБКА обновления БД для #{post_id}: {db_err}")
                # Продолжаем несмотря на ошибку БД
            
            # === VK ПУБЛИКАЦИЯ (ОПЦИОНАЛЬНАЯ, НЕ КРИТИЧНА) ===
            if tg_success:
                try:
                    vk_result = await publisher.publish_to_vk(
                        text=text,
                        image=image_bytes,
                        add_signature=True
                    )
                    if vk_result:
                        logger.info(f"✅ VK публикация #{post_id}")
                    else:
                        logger.warning(f"⚠️ VK вернул False для #{post_id}, но TG OK")
                except Exception as vk_err:
                    # VK упал - но это не критично, пост уже в TG
                    logger.warning(f"⚠️ VK публикация #{post_id} упала (TG уже опубликован): {type(vk_err).__name__}: {vk_err}")

        except Exception as critical_err:
            logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА для поста #{post_id}: {critical_err}")
            # Продолжаем со следующего поста
            continue

    logger.info("✅ Цикл автопубликации завершён")


async def main():
    from aiogram import Bot, Dispatcher
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.client.default import DefaultBotProperties
    from config import CONTENT_BOT_TOKEN
    from handlers.content_bot import content_router
    from database.db import db
    from utils.bot_config import set_content_bot, set_scheduler

    await db.connect()
    bot = Bot(token=CONTENT_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    set_content_bot(bot)

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(content_router)

    me = await bot.get_me()
    logger.info(f"🚀 Контент-бот: @{me.username}")

    # Запускаем планировщик автопубликации
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(publish_scheduled_posts, 'interval', minutes=1, args=[bot])
    scheduler.start()
    set_scheduler(scheduler)
    logger.info("✅ Планировщик автопубликации запущен (интервал: 1 минута)")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
