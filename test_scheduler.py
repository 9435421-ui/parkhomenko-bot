import asyncio
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

# Добавляем корень проекта в путь
sys.path.append(os.getcwd())

from content_bot_mvp.database.db import db
from content_bot_mvp.services.scheduler import ContentScheduler

async def test_scheduler():
    await db.connect()

    # Подготавливаем данные: один пост на сейчас
    async with db.conn.cursor() as cursor:
        await cursor.execute(
            "INSERT INTO content_items (title, body, status, bot_name, created_by) VALUES (?, ?, ?, ?, ?)",
            ("Плановый пост", "Текст", "scheduled", "TestBot", 1)
        )
        item_id = cursor.lastrowid
        await cursor.execute(
            "INSERT INTO content_plan (content_item_id, scheduled_at) VALUES (?, ?)",
            (item_id, datetime.now() - timedelta(minutes=1))
        )
        await db.conn.commit()

    # Мокаем TelegramPublisher.publish_item
    with patch('content_bot_mvp.services.scheduler.TelegramPublisher') as MockPublisher:
        instance = MockPublisher.return_value
        instance.publish_item = AsyncMock(return_value=True)

        scheduler = ContentScheduler(MagicMock())
        await scheduler.check_and_publish()

        print(f"Publisher called: {instance.publish_item.called}", flush=True)

        # Проверяем статус в плане
        async with db.conn.execute("SELECT published FROM content_plan WHERE content_item_id = ?", (item_id,)) as cursor:
            row = await cursor.fetchone()
            print(f"Published in plan: {bool(row['published'])}", flush=True)

    await db.conn.close()

if __name__ == "__main__":
    asyncio.run(test_scheduler())
