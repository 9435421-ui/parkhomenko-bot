from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database.db import db
from datetime import datetime
from services.workflow_service import workflow

router = Router()

class ReviewStates(StatesGroup):
    waiting_for_edit = State()
    waiting_for_schedule_time = State()

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

# --- CALLBACK HANDLERS FOR REVIEW ---

@router.callback_query(F.data.startswith("pub_approve_"))
async def process_approve(callback: CallbackQuery, role: str):
    item_id = int(callback.data.replace("pub_approve_", ""))

    success = await workflow.move_to_status(item_id, 'approved', callback.from_user.id, role)
    if success:
        await callback.message.edit_text(callback.message.text + "\n\n✅ <b>УТВЕРЖДЕНО</b>", parse_mode="HTML")

        # Предлагаем опубликовать сейчас или запланировать
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Опубликовать сейчас", callback_data=f"pub_now_{item_id}")],
            [InlineKeyboardButton(text="⏰ Запланировать", callback_data=f"pub_sched_{item_id}")]
        ])
        await callback.message.answer(f"Пост #{item_id} утвержден. Что дальше?", reply_markup=markup)
    else:
        await callback.answer("❌ Ошибка при утверждении.")

@router.callback_query(F.data.startswith("pub_now_"))
async def process_publish_now(callback: CallbackQuery, role: str):
    item_id = int(callback.data.replace("pub_now_", ""))

    # Получаем айтем
    async with db.conn.execute("SELECT bot_name FROM content_items WHERE id = ?", (item_id,)) as cursor:
        item = await cursor.fetchone()

    from services.publisher_tg import TelegramPublisher
    publisher = TelegramPublisher(callback.bot)
    success = await publisher.publish_item(item_id, bot_name=item['bot_name'])

    if success:
        await callback.message.edit_text(callback.message.text + "\n\n🚀 <b>ОПУБЛИКОВАНО</b>", parse_mode="HTML")
    else:
        await callback.answer("❌ Ошибка публикации.")

@router.callback_query(F.data.startswith("pub_edit_"))
async def process_edit(callback: CallbackQuery, state: FSMContext):
    item_id = int(callback.data.replace("pub_edit_", ""))
    await state.update_data(edit_item_id=item_id)
    await callback.message.answer(f"Введите новый текст для поста #{item_id}:")
    await state.set_state(ReviewStates.waiting_for_edit)

@router.message(ReviewStates.waiting_for_edit)
async def process_edit_text(message: Message, state: FSMContext):
    data = await state.get_data()
    item_id = data['edit_item_id']

    async with db.conn.cursor() as cursor:
        await cursor.execute("UPDATE content_items SET body = ?, updated_at = ? WHERE id = ?",
                           (message.text, datetime.now(), item_id))
        await db.conn.commit()

    await message.answer(f"✅ Текст поста #{item_id} обновлен. Используйте /review_queue для проверки.")
    await state.clear()

@router.callback_query(F.data.startswith("pub_sched_"))
async def process_schedule_init(callback: CallbackQuery, state: FSMContext):
    item_id = int(callback.data.replace("pub_sched_", ""))
    await state.update_data(sched_item_id=item_id)
    await callback.message.answer(f"Введите дату и время публикации для поста #{item_id}\nФормат: YYYY-MM-DD HH:MM")
    await state.set_state(ReviewStates.waiting_for_schedule_time)

@router.message(ReviewStates.waiting_for_schedule_time)
async def process_schedule_time(message: Message, state: FSMContext, role: str):
    data = await state.get_data()
    item_id = data['sched_item_id']

    try:
        scheduled_at = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте YYYY-MM-DD HH:MM (например: 2024-12-31 23:59)")
        return

    success = await workflow.move_to_status(item_id, 'scheduled', message.from_user.id, role)
    if success:
        async with db.conn.cursor() as cursor:
            # Обновляем content_plan
            await cursor.execute("DELETE FROM content_plan WHERE content_item_id = ?", (item_id,))
            await cursor.execute("INSERT INTO content_plan (content_item_id, scheduled_at) VALUES (?, ?)",
                               (item_id, scheduled_at))
            await db.conn.commit()
        await message.answer(f"✅ Пост #{item_id} запланирован на {message.text}.")
    else:
        await message.answer("❌ Ошибка при смене статуса на SCHEDULED.")

    await state.clear()
