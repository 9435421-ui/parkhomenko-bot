from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from database.db import db

router = Router()

from services.workflow_service import workflow

@router.message(Command("review_queue"))
async def cmd_review_queue(message: Message):
    async with db.conn.cursor() as cursor:
        await cursor.execute(
            "SELECT id, title, status FROM content_items WHERE status = 'review' ORDER BY updated_at ASC"
        )
        rows = await cursor.fetchall()

    if not rows:
        await message.answer("Очередь пуста. Нет постов на проверку. ☕")
        return

    text = "🧐 Очередь на утверждение:\n\n"
    for row in rows:
        text += f"ID: {row['id']} | {row['title']}\n"

    await message.answer(text + "\nИспользуйте /approve [ID] или /reject [ID]")

@router.message(Command("approve"))
async def cmd_approve(message: Message, role: str):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /approve [ID]")
        return

    try:
        item_id = int(args[1])
    except ValueError:
        await message.answer("ID должен быть числом.")
        return

    success = await workflow.move_to_status(item_id, 'approved', message.from_user.id, role)
    if success:
        await message.answer(f"✅ Пост #{item_id} утвержден (APPROVED).")
    else:
        await message.answer(f"❌ Не удалось утвердить пост #{item_id}. Проверьте статус и ваши права.")

@router.message(Command("schedule"))
async def cmd_schedule(message: Message, role: str):
    args = message.text.split()
    if len(args) < 4:
        await message.answer("🕒 Использование: /schedule [ID] [YYYY-MM-DD] [HH:MM]")
        return

    try:
        item_id = int(args[1])
        date_str = f"{args[2]} {args[3]}"
        scheduled_at = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
    except ValueError as e:
        await message.answer(f"❌ Ошибка формата: {e}")
        return

    success = await workflow.move_to_status(item_id, 'scheduled', message.from_user.id, role)
    if success:
        # Добавляем в план
        async with db.conn.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO content_plan (content_item_id, scheduled_at) VALUES (?, ?)",
                (item_id, scheduled_at)
            )
            await db.conn.commit()
        await message.answer(f"✅ Пост #{item_id} запланирован на {date_str}.")
    else:
        await message.answer(f"❌ Не удалось изменить статус на SCHEDULED.")

@router.message(Command("publish_now"))
async def cmd_publish_now(message: Message, role: str):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("🚀 Мгновенная публикация: /publish_now [ID]\nНужен статус APPROVED.")
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
