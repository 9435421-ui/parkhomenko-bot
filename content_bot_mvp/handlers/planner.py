from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database.db import db

router = Router()

class PostStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_body = State()

@router.message(Command("new_post"))
async def cmd_new_post(message: Message, state: FSMContext):
    await message.answer("📝 Введите заголовок (тему) нового поста:")
    await state.set_state(PostStates.waiting_for_title)

@router.message(PostStates.waiting_for_title)
async def process_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("📥 Теперь введите основной текст поста:")
    await state.set_state(PostStates.waiting_for_body)

@router.message(PostStates.waiting_for_body)
async def process_body(message: Message, state: FSMContext):
    data = await state.get_data()
    title = data['title']
    body = message.text

    # Сохраняем как идею/черновик
    async with db.conn.cursor() as cursor:
        await cursor.execute(
            "INSERT INTO content_items (title, body, status, created_by) VALUES (?, ?, 'idea', ?)",
            (title, body, message.from_user.id)
        )
        item_id = cursor.lastrowid
        await db.conn.commit()

    await state.clear()
    await message.answer(f"✅ Пост «{title}» сохранен со статусом IDEA (ID: {item_id}).\nИспользуйте /my_posts для управления.")

@router.message(Command("my_posts"))
async def cmd_my_posts(message: Message):
    async with db.conn.cursor() as cursor:
        await cursor.execute(
            "SELECT id, title, status FROM content_items WHERE created_by = ? ORDER BY created_at DESC LIMIT 10",
            (message.from_user.id,)
        )
        rows = await cursor.fetchall()

    if not rows:
        await message.answer("У вас пока нет созданных постов.")
        return

    text = "📂 Ваши последние посты:\n\n"
    for row in rows:
        text += f"ID: {row['id']} | [{row['status']}] {row['title']}\n"

    await message.answer(text)
