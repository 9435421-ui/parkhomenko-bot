from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database.db import db
from keyboards.review_keyboards import get_review_keyboard
import os
from datetime import datetime

router = Router()

# In real life this would be in .env
REVIEW_GROUP_ID = os.getenv("LEADS_GROUP_CHAT_ID", "-1003370698977")

class PostReview(StatesGroup):
    entering_schedule_time = State()
    editing_post_body = State()

async def notify_review_group(bot: Bot, post_id: int):
    post = await db.get_post(post_id)
    if not post:
        return

    review_text = (
        f"📝 <b>НА ПРОВЕРКЕ: Пост #{post['id']}</b>\n"
        f"🎯 Канал: {post['target_channel_alias']}\n"
        f"🏷 Бренд: {post['brand']}\n"
        f"📂 Тема: {post['type']}\n\n"
        f"{post['body']}\n\n"
        f"🔗 CTA: {post['cta_link']}\n"
        f"🖼 Изображение: {post['image_description'] or 'не указано'}"
    )

    await bot.send_message(
        chat_id=REVIEW_GROUP_ID,
        text=review_text,
        reply_markup=get_review_keyboard(post_id),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("approve:"))
async def approve_post(callback: CallbackQuery):
    post_id = int(callback.data.split(":")[1])
    await db.update_post(post_id, status='approved')

    await db.add_audit_log(
        action="approve_post",
        user_id=callback.from_user.id,
        details=f"Post #{post_id} approved"
    )

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>УТВЕРЖДЕНО</b>",
        parse_mode="HTML"
    )
    await callback.answer("✅ Пост утвержден")

@router.callback_query(F.data.startswith("schedule:"))
async def schedule_post_start(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split(":")[1])
    await state.update_data(scheduling_post_id=post_id)
    await state.set_state(PostReview.entering_schedule_time)

    await callback.message.answer("⏰ Введите дату и время публикации в формате ГГГГ-ММ-ДД ЧЧ:ММ:")
    await callback.answer()

@router.message(PostReview.entering_schedule_time)
async def schedule_time_entered(message: Message, state: FSMContext):
    data = await state.get_data()
    post_id = data.get('scheduling_post_id')

    try:
        publish_date = datetime.strptime(message.text, "%Y-%m-%d %H:%M")
        await db.update_post(post_id, status='scheduled', publish_date=publish_date)

        await db.add_audit_log(
            action="schedule_post",
            user_id=message.from_user.id,
            details=f"Post #{post_id} scheduled for {message.text}"
        )

        await message.answer(f"✅ Пост #{post_id} запланирован на {message.text}")
        await state.clear()
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте ГГГГ-ММ-ДД ЧЧ:ММ (например, 2026-02-01 12:00):")

@router.callback_query(F.data.startswith("edit:"))
async def edit_post_start(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split(":")[1])
    post = await db.get_post(post_id)
    if not post:
        await callback.answer("❌ Пост не найден", show_alert=True)
        return

    await state.update_data(editing_post_id=post_id)
    await state.set_state(PostReview.editing_post_body)

    await callback.message.answer(f"✏️ <b>Редактирование поста #{post_id}</b>\n\nТекущий текст:\n<code>{post['body']}</code>\n\nВведите новый текст поста:", parse_mode="HTML")
    await callback.answer()

@router.message(PostReview.editing_post_body)
async def post_body_edited(message: Message, state: FSMContext):
    data = await state.get_data()
    post_id = data.get('editing_post_id')
    new_body = message.text

    await db.update_post(post_id, body=new_body)

    await db.add_audit_log(
        action="edit_post",
        user_id=message.from_user.id,
        details=f"Post #{post_id} body updated"
    )

    await message.answer(f"✅ Текст поста #{post_id} обновлен.")
    await state.clear()

    # Notify group again with updated text
    await notify_review_group(message.bot, post_id)
