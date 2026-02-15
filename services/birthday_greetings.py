"""
Поздравления с ДР в личные сообщения подписчикам.
Запускается по расписанию (cron 9:00); использует clients_birthdays и main_bot.
"""
import logging
from aiogram import Bot

logger = logging.getLogger(__name__)


async def send_birthday_greetings(bot: Bot):
    """Отправить поздравления с ДР в личку подписчикам из clients_birthdays (у кого сегодня ДР и ещё не отправлено)."""
    from database import db
    try:
        birthdays = await db.get_today_birthdays()
        if not birthdays:
            logger.info("Поздравления с ДР: никого нет на сегодня")
            return
        agent = None
        for row in birthdays:
            user_id = row.get("user_id")
            name = (row.get("name") or "друг").strip() or "друг"
            birthday_id = row.get("id")
            try:
                try:
                    from content_agent import ContentAgent
                    agent = agent or ContentAgent()
                    post = await agent.generate_greeting_post(person_name=name, occasion="день рождения")
                    text = (post.get("title") or "") + "\n\n" + (post.get("body") or "")
                except Exception:
                    text = f"🎂 {name}, с днём рождения! Желаем здоровья, счастья и уюта в вашем доме!"
                if not text.strip():
                    text = f"🎂 {name}, с днём рождения!"
                await bot.send_message(user_id, text)
                await db.mark_birthday_greeting_sent(birthday_id)
                logger.info(f"Поздравление с ДР отправлено user_id={user_id}")
            except Exception as e:
                logger.warning(f"Не удалось отправить поздравление user_id={user_id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка отправки поздравлений с ДР: {e}")
