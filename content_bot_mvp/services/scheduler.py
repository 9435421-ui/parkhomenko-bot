import asyncio
import logging
from datetime import datetime
from content_bot_mvp.database.db import db
from content_bot_mvp.services.publisher_tg import TelegramPublisher

class ContentScheduler:
    def __init__(self, bot):
        self.publisher = TelegramPublisher(bot)

    async def run(self):
        """Основной цикл планировщика"""
        logging.info("Scheduler started")
        while True:
            try:
                await self.check_and_publish()
            except Exception as e:
                logging.error(f"Scheduler error: {e}")
            await asyncio.sleep(60) # Проверка каждую минуту

    async def check_and_publish(self):
        now = datetime.now()
        async with db.conn.execute(
            """SELECT cp.id, cp.content_item_id, ci.bot_name, ci.status, ci.quiz_link
               FROM content_plan cp
               JOIN content_items ci ON cp.content_item_id = ci.id
               WHERE cp.published = 0
               AND cp.scheduled_at <= ?
               AND ci.status IN ('approved', 'scheduled')
               AND ci.quiz_link IS NOT NULL""",
            (now,)
        ) as cursor:
            tasks = await cursor.fetchall()

        for task in tasks:
            logging.info(f"Publishing scheduled item {task['content_item_id']}")
            success = await self.publisher.publish_item(task['content_item_id'], bot_name=task['bot_name'])
            if success:
                async with db.conn.cursor() as cursor:
                    await cursor.execute(
                        "UPDATE content_plan SET published = 1, published_at = ? WHERE id = ?",
                        (datetime.now(), task['id'])
                    )
                    await db.conn.commit()
            else:
                async with db.conn.cursor() as cursor:
                    await cursor.execute(
                        "UPDATE content_plan SET error_log = 'Failed to publish' WHERE id = ?",
                        (task['id'],)
                    )
                    await db.conn.commit()

async def start_scheduler(bot):
    scheduler = ContentScheduler(bot)
    await scheduler.run()
