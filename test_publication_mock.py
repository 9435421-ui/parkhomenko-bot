import asyncio
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock

# Добавляем корень проекта в путь
sys.path.append(os.getcwd())

from content_bot_mvp.database.db import db
from content_bot_mvp.services.publisher_tg import TelegramPublisher

async def test_publication_logic():
    await db.connect()

    # Подготавливаем данные
    async with db.conn.cursor() as cursor:
        await cursor.execute(
            "INSERT OR REPLACE INTO bots_channels (bot_name, bot_token, tg_channel_id, platform) VALUES (?, ?, ?, ?)",
            ("TestBot", "FAKE_TOKEN", "@test_channel", "TG")
        )
        await cursor.execute(
            "INSERT INTO content_items (title, body, status, bot_name, created_by) VALUES (?, ?, ?, ?, ?)",
            ("Заголовок", "Текст поста", "approved", "TestBot", 1)
        )
        item_id = cursor.lastrowid
        await db.conn.commit()

    # Мокаем aiogram Bot
    mock_bot_instance = MagicMock()
    mock_bot_instance.send_message = AsyncMock(return_value=MagicMock(message_id=12345))
    mock_bot_instance.__aenter__ = AsyncMock(return_value=mock_bot_instance)
    mock_bot_instance.__aexit__ = AsyncMock()

    with patch('content_bot_mvp.services.publisher_tg.Bot', return_value=mock_bot_instance):
        publisher = TelegramPublisher(mock_bot_instance)
        success = await publisher.publish_item(item_id, bot_name="TestBot")

        print(f"Publication success: {success}", flush=True)

        if success:
            # Проверяем вызов send_message
            args, kwargs = mock_bot_instance.send_message.call_args
            print(f"Sent to chat: {kwargs['chat_id']}", flush=True)
            print(f"Text starts with: {kwargs['text'][:20]}...", flush=True)
            print(f"Reply markup exists: {kwargs['reply_markup'] is not None}", flush=True)

            # Проверяем статус в БД
            async with db.conn.execute("SELECT status FROM content_items WHERE id = ?", (item_id,)) as cursor:
                row = await cursor.fetchone()
                print(f"New status in DB: {row['status']}", flush=True)

    await db.conn.close()

if __name__ == "__main__":
    asyncio.run(test_publication_logic())
