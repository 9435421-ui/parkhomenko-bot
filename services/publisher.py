import asyncio
import logging
import os
from datetime import datetime
from functools import partial
from html import escape
import inspect
from database.db import db
from services.image_generator import ImageAgent
from config import CONTENT_CHANNEL_ID, LEADS_GROUP_CHAT_ID, THREAD_ID_LOGS, YANDEX_API_KEY, FOLDER_ID

logger = logging.getLogger(__name__)

class AutoPoster:
    """Класс для автоматической публикации контента в канал"""

    def __init__(self, bot):
        self.bot = bot
        self.channel_id = CONTENT_CHANNEL_ID
        
        send_msg_method = getattr(bot, 'send_message', None)
        if send_msg_method is None:
            self.is_async = False
        else:
            original_func = getattr(send_msg_method, '__func__', send_msg_method)
            unwrapped_func = inspect.unwrap(original_func)
            self.is_async = inspect.iscoroutinefunction(unwrapped_func)

    async def publish_all(self, text: str, image_bytes: bytes = None):
        """Публикация во все каналы (TG + VK)"""
        # Telegram
        try:
            if image_bytes:
                from aiogram.types import BufferedInputFile
                photo = BufferedInputFile(image_bytes, filename="post.jpg")
                await self.bot.send_photo(chat_id=self.channel_id, photo=photo, caption=text, parse_mode='HTML')
            else:
                await self.bot.send_message(chat_id=self.channel_id, text=text, parse_mode='HTML')
            logger.info("✅ Пост опубликован в Telegram")
        except Exception as e:
            logger.error(f"❌ Ошибка публикации в Telegram: {e}")

        # VK (заглушка)
        logger.info("ℹ️ Публикация в VK пока не реализована")

    async def check_and_publish(self):
        """Проверяет и публикует готовые посты из БД"""
        try:
            posts = await db.get_posts_to_publish()
            if not posts:
                return

            for post in posts:
                try:
                    title = post.get('title', '')
                    body = post.get('body', '')
                    cta = post.get('cta', '')
                    
                    text = f"<b>{title}</b>\n\n{body}\n\n{cta}" if title else f"{body}\n\n{cta}"
                    
                    image_url = post.get('image_url')
                    image_bytes = None
                    
                    if image_url and image_url.startswith('http'):
                        import aiohttp
                        async with aiohttp.ClientSession() as session:
                            async with session.get(image_url) as resp:
                                if resp.status == 200:
                                    image_bytes = await resp.read()

                    await self.publish_all(text, image_bytes)
                    await db.mark_as_published(post['id'])
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка публикации поста #{post.get('id')}: {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в check_and_publish: {e}")

publisher = None # Будет инициализирован в main.py
