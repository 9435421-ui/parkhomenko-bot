import asyncio
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from content_bot_mvp.database.db import db

class BroadcastService:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def start_broadcast(self, user_ids: list, text: str, admin_id: int):
        """Запуск рассылки с троттлингом"""
        logging.info(f"Начало рассылки на {len(user_ids)} пользователей")

        success_count = 0
        fail_count = 0

        for user_id in user_ids:
            try:
                await self.bot.send_message(user_id, text)
                success_count += 1
                # Пауза для соблюдения лимитов Telegram (30 сообщений в секунду)
                await asyncio.sleep(0.05)
            except TelegramRetryAfter as e:
                logging.warning(f"Flood limit reached. Sleeping for {e.retry_after}s")
                await asyncio.sleep(e.retry_after)
                await self.bot.send_message(user_id, text)
                success_count += 1
            except Exception as e:
                logging.error(f"Ошибка рассылки пользователю {user_id}: {e}")
                fail_count += 1

        summary = f"📢 Рассылка завершена.\nУспешно: {success_count}\nОшибок: {fail_count}"
        await db.log_action(admin_id, "broadcast_finished", summary)
        return summary
