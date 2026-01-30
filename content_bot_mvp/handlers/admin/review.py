from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from database.db import db

router = Router()

@router.message(Command("review_queue"))
async def cmd_review_queue(message: Message):
    async with db.conn.cursor() as cursor:
        await cursor.execute(
            "SELECT id, title, status FROM content_items WHERE status = 'review' ORDER BY updated_at ASC"
        )
        rows = await cursor.fetchall()

    if not rows:
        await message.answer("Queue is empty. No posts waiting for review. ☕")
        return

    text = "🧐 Очередь на утверждение:\n\n"
    for row in rows:
        text += f"ID: {row['id']} | {row['title']}\n"

    await message.answer(text)

@router.message(Command("schedule"))
async def cmd_schedule(message: Message):
    await message.answer("🕒 Функция планирования: используйте /schedule [ID] [ГГГГ-ММ-ДД ЧЧ:ММ]\n(В MVP реализован базовый выбор поста для расписания)")

@router.message(Command("publish_now"))
async def cmd_publish_now(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("🚀 Мгновенная публикация: отправьте /publish_now [ID]\nПост должен иметь статус APPROVED.")
        return

    try:
        item_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return

    # Получаем айтем и проверяем статус
    async with db.conn.execute("SELECT status, bot_name FROM content_items WHERE id = ?", (item_id,)) as cursor:
        item = await cursor.fetchone()
        if not item:
            await message.answer("❌ Пост не найден.")
            return

        if item['status'] != 'approved':
            await message.answer(f"❌ Пост должен иметь статус APPROVED (текущий: {item['status']}).")
            return

    from services.publisher_tg import TelegramPublisher
    publisher = TelegramPublisher(message.bot)

    success = await publisher.publish_item(item_id, bot_name=item['bot_name'])

    if success:
        await message.answer(f"✅ Пост #{item_id} успешно опубликован через {item['bot_name']}!")
    else:
        await message.answer(f"❌ Ошибка при публикации поста #{item_id}. Проверьте логи.")
