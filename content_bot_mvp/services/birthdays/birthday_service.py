import asyncio
import logging
from datetime import datetime
from aiogram import Bot
from content_bot_mvp.database.db import db

class BirthdayService:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def check_and_congratulate(self):
        """Проверка именинников и отправка поздравлений"""
        today = datetime.now().date()
        today_str = today.strftime("%m-%d") # Сравнение по месяцу и дню

        async with db.conn.execute(
            "SELECT * FROM birthdays WHERE is_active = 1 AND strftime('%m-%d', birth_date) = ?",
            (today_str,)
        ) as cursor:
            rows = await cursor.fetchall()

            for row in rows:
                if row['last_congratulated_year'] == today.year:
                    continue # Уже поздравляли в этом году

                await self._send_congratulation(row)

                # Обновляем год последнего поздравления
                await db.conn.execute(
                    "UPDATE birthdays SET last_congratulated_year = ? WHERE id = ?",
                    (today.year, row['id'])
                )
            await db.conn.commit()

    async def _send_congratulation(self, user_row):
        try:
            text = (
                f"🎉 {user_row['name']}, команда ТЕРИОН поздравляет вас с днем рождения!\n\n"
                "Желаем уюта в доме, успешных начинаний и только приятных перемен. "
                "Пусть ваши мечты о идеальном пространстве всегда сбываются!"
            )
            await self.bot.send_message(user_row['user_id'], text)
            await db.log_action(0, "birthday_sent", f"User ID: {user_row['user_id']}")
        except Exception as e:
            logging.error(f"Ошибка отправки поздравления пользователю {user_row['user_id']}: {e}")

    async def run_scheduler(self):
        """Фоновый цикл для ежедневной проверки (упрощенно для MVP)"""
        while True:
            await self.check_and_congratulate()
            # Проверка раз в сутки (86400 секунд)
            await asyncio.sleep(86400)
