import logging
import asyncio
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from content_bot_mvp.database.db import db

class BroadcastService:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_broadcast(self, user_ids: list, text: str, image_url: str = None):
        """Массовая рассылка с троттлингом"""
        success_count = 0
        error_count = 0

        for user_id in user_ids:
            try:
                if image_url:
                    await self.bot.send_photo(chat_id=user_id, photo=image_url, caption=text, parse_mode="HTML")
                else:
                    await self.bot.send_message(chat_id=user_id, text=text, parse_mode="HTML")

                success_count += 1
                # Троттлинг: максимум 30 сообщений в секунду по лимитам TG
                await asyncio.sleep(0.05)

            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
                # Повторная попытка
                await self.bot.send_message(chat_id=user_id, text=text)
                success_count += 1
            except Exception as e:
                logging.error(f"Error sending to {user_id}: {e}")
                error_count += 1

        await db.log_action(0, "broadcast_completed", f"Success: {success_count}, Errors: {error_count}")
        return success_count, error_count
