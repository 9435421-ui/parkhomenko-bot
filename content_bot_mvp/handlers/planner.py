from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database.db import db
from services.workflow_service import workflow
from services.content_generator import generator
from config.settings import settings

router = Router()

class PostStates(StatesGroup):
    waiting_for_channel = State()
    waiting_for_topic = State()
    waiting_for_generation = State()

@router.message(Command("new_post"))
async def cmd_new_post(message: Message, state: FSMContext):
    # Выбор канала
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="TORION", callback_data="sel_chan_torion_main")],
        [InlineKeyboardButton(text="DomGrand", callback_data="sel_chan_domgrand")]
    ])
    await message.answer("📢 Выберите канал для публикации:", reply_markup=markup)
    await state.set_state(PostStates.waiting_for_channel)

@router.callback_query(PostStates.waiting_for_channel, F.data.startswith("sel_chan_"))
async def process_channel_select(callback: CallbackQuery, state: FSMContext):
    channel_alias = callback.data.replace("sel_chan_", "")
    await state.update_data(channel_alias=channel_alias)

    # Выбор темы
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Перепланировка кухни", callback_data="sel_topic_kitchen")],
        [InlineKeyboardButton(text="Объединение санузла", callback_data="sel_topic_bathroom")],
        [InlineKeyboardButton(text="Своя тема (введите текстом)", callback_data="sel_topic_manual")]
    ])
    await callback.message.edit_text(f"Выбран канал: {channel_alias}\n\n📝 Выберите тему поста:", reply_markup=markup)
    await state.set_state(PostStates.waiting_for_topic)

@router.callback_query(PostStates.waiting_for_topic, F.data.startswith("sel_topic_"))
async def process_topic_select(callback: CallbackQuery, state: FSMContext):
    topic_data = callback.data.replace("sel_topic_", "")
    if topic_data == "manual":
        await callback.message.answer("Введите вашу тему текстом:")
        return

    topics = {
        "kitchen": "Перепланировка и объединение кухни с гостиной",
        "bathroom": "Согласование объединения ванной и туалета"
    }
    await state.update_data(topic=topics.get(topic_data))
    await generate_and_save_draft(callback.message, state)

@router.message(PostStates.waiting_for_topic)
async def process_manual_topic(message: Message, state: FSMContext):
    await state.update_data(topic=message.text)
    await generate_and_save_draft(message, state)

async def generate_and_save_draft(message: Message, state: FSMContext):
    data = await state.get_data()
    channel_alias = data['channel_alias']
    topic = data['topic']

    msg = await message.answer(f"🤖 Генерирую пост на тему «{topic}» для канала {channel_alias}...")

    # Генерация текста
    body = await generator.generate_post_text(topic, "educational", channel_alias)
    hashtags = generator.get_hashtags(channel_alias)
    quiz_link = generator.get_quiz_link(channel_alias)

    # Сохраняем в БД как REVIEW (сразу на проверку)
    async with db.conn.cursor() as cursor:
        await cursor.execute(
            """INSERT INTO content_items
               (title, body, hashtags, quiz_link, target_channel_alias, status, created_by, bot_name)
               VALUES (?, ?, ?, ?, ?, 'review', ?, 'domgrad_content')""",
            (topic, body, hashtags, quiz_link, channel_alias, message.from_user.id if hasattr(message, 'from_user') and message.from_user else 0)
        )
        item_id = cursor.lastrowid
        await db.conn.commit()

    # Отправка в рабочую группу (Admin Group)
    admin_chat_id = settings.ADMIN_TELEGRAM_ID

    preview_text = (
        f"📝 <b>НОВЫЙ ЧЕРНОВИК ПОСТА #{item_id}</b>\n"
        f"📢 Канал: {channel_alias}\n"
        f"📋 Тема: {topic}\n"
        f"-------------------\n\n"
        f"{body}\n\n"
        f"{hashtags}\n\n"
        f"👉 Консультация: {quiz_link}"
    )

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Утвердить", callback_data=f"pub_approve_{item_id}")],
        [InlineKeyboardButton(text="✏️ Править", callback_data=f"pub_edit_{item_id}")],
        [InlineKeyboardButton(text="⏰ Запланировать", callback_data=f"pub_sched_{item_id}")]
    ])

    try:
        await message.bot.send_message(chat_id=admin_chat_id, text=preview_text, reply_markup=markup, parse_mode="HTML")
        await msg.edit_text(f"✅ Черновик #{item_id} создан и отправлен на согласование в рабочую группу.")
    except Exception as e:
        await msg.edit_text(f"⚠️ Черновик #{item_id} создан, но не удалось отправить в группу: {e}")

    await state.clear()

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

    await message.answer(text + "\nДля изменения статуса используйте /submit_to_review [ID]")

@router.message(Command("submit_to_review"))
async def cmd_submit_review(message: Message, role: str):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /submit_to_review [ID]")
        return

    try:
        item_id = int(args[1])
    except ValueError:
        await message.answer("ID должен быть числом.")
        return

    # Сначала в draft, потом в review (цепочка: idea -> draft -> review)
    # Попробуем сразу в review если это позволено, но workflow может ограничить

    # Сначала переводим в DRAFT
    success_draft = await workflow.move_to_status(item_id, 'draft', message.from_user.id, role)
    if success_draft:
        # Пытаемся перевести в REVIEW
        success_review = await workflow.move_to_status(item_id, 'review', message.from_user.id, role)
        if success_review:
            await message.answer(f"✅ Пост #{item_id} отправлен на проверку (REVIEW).")
        else:
            await message.answer(f"✅ Пост #{item_id} сохранен как черновик (DRAFT).")
    else:
        await message.answer(f"❌ Не удалось изменить статус поста #{item_id}. Проверьте текущий статус.")
