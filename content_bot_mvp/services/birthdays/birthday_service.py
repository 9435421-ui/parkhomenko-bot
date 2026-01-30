import logging
import asyncio
from datetime import datetime
from aiogram import Bot
from content_bot_mvp.database.db import db

class BirthdayService:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def check_and_send_greetings(self):
        """Проверяет именинников на сегодня и отправляет поздравления"""
        today = datetime.now().strftime("%m-%d")

        async with db.conn.execute(
            "SELECT id, user_id, name FROM birthdays WHERE strftime('%m-%d', birth_date) = ? AND sent = 0",
            (today,)
        ) as cursor:
            birthdays = await cursor.fetchall()

        for bday in birthdays:
            try:
                await self.bot.send_message(
                    chat_id=bday['user_id'],
                    text=f"🎉 С днем рождения, {bday['name']}! Желаем вам уюта в доме и успешных перепланировок! 🏠"
                )
                await db.conn.execute("UPDATE birthdays SET sent = 1 WHERE id = ?", (bday['id'],))
                await db.conn.commit()
                await db.log_action(0, "birthday_greeting_sent", f"User: {bday['user_id']}", status="success")
                logging.info(f"Sent birthday greeting to {bday['user_id']}")
            except Exception as e:
                logging.error(f"Failed to send birthday greeting to {bday['user_id']}: {e}")

    async def run_scheduler(self):
        """Запуск ежедневной проверки"""
        while True:
            await self.check_and_send_greetings()
            # Ждем до следующего дня (проверка раз в сутки в 10 утра, например)
            # Для MVP просто ждем 24 часа
            await asyncio.sleep(86400)
