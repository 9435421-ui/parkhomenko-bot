import asyncio
import logging
import os
from datetime import datetime
import pytz
from aiogram import Bot
from aiogram.types import FSInputFile
from dotenv import load_dotenv
from database import db

# Загрузка переменных окружения
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CONTENT_CHANNEL_ID")  # Используем CONTENT_CHANNEL_ID из .env

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN must be set in .env")
if not CHANNEL_ID:
    raise RuntimeError("CONTENT_CHANNEL_ID must be set in .env")

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация асинхронного бота (aiogram)
bot = Bot(token=BOT_TOKEN)

async def run_autoposter():
    """
    Запуск автопостинга запланированных постов
    """
    logger.info("🚀 Автопостер запущен. Проверка каждые 30-60 секунд.")

    while True:
        try:
            # Получаем посты для отправки
            posts_to_send = await db.get_scheduled_posts_to_send()

            if not posts_to_send:
                logger.info("Нет запланированных постов для отправки")
            else:
                logger.info(f"Найдено {len(posts_to_send)} постов для отправки")

                for post in posts_to_send:
                    try:
                        post_id = post['id']
                        channel_id = post['channel_id']
                        text = post['text']
                        image_path = post['image_path']
                        scheduled_at = post['scheduled_at']

                        logger.info(f"Отправка поста #{post_id}, запланирован на {scheduled_at}")

                        # Отправляем пост асинхронно
                        if image_path and image_path.strip():
                            # Отправляем фото с подписью (асинхронно через aiogram)
                            photo_file = FSInputFile(image_path)
                            await bot.send_photo(chat_id=channel_id, photo=photo_file, caption=text)
                        else:
                            # Отправляем текстовое сообщение (асинхронно)
                            await bot.send_message(chat_id=channel_id, text=text)

                        # Отмечаем как отправленный
                        await db.mark_scheduled_post_as_sent(post_id)

                        logger.info(f"✅ Пост #{post_id} успешно отправлен")

                        # Небольшая пауза между постами
                        await asyncio.sleep(1)

                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки поста #{post['id']}: {e}")
                        continue

        except Exception as e:
            logger.error(f"❌ Критическая ошибка в run_autoposter: {e}")

        # Пауза между проверками (30-60 секунд, используем 45)
        await asyncio.sleep(45)

async def main():
    """Главная функция"""
    # Подключаемся к БД
    await db.connect()

    try:
        # Запускаем автопостер
        await run_autoposter()
    finally:
        # Закрываем сессию бота и отключаемся от БД
        await bot.session.close()
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
