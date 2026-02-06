import os
import hashlib
import base64
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, BufferedInputFile, InputMediaPhoto
)
from aiogram.fsm.context import FSMContext
from config import (
    THREAD_ID_DRAFTS, NOTIFICATIONS_CHANNEL_ID, CHANNEL_ID,
    BOT_TOKEN, MINI_APP_URL
)
from services.vk_service import vk_service
from database.db import db
from utils.router_ai import router_ai
from utils.image_gen import image_gen
import json

media_router = Router()

def get_post_markup(post_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Опубликовать везде", callback_data=f"publish_all:{post_id}")],
        [InlineKeyboardButton(text="📢 Только в TG", callback_data=f"publish_tg:{post_id}")],
        [InlineKeyboardButton(text="💙 Только в VK", callback_data=f"publish_vk:{post_id}")],
        [InlineKeyboardButton(text="🪄 Оформить пост (DeepSeek)", callback_data=f"expert:improve_draft:{post_id}")],
        [InlineKeyboardButton(text="🖼 Создать визуал (Flux)", callback_data=f"expert:image_for_post:{post_id}")],
        [InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_draft:{post_id}")]
    ])

def get_expert_tools_markup():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪄 Оформить пост", callback_data="expert:improve")],
        [InlineKeyboardButton(text="🖼 Создать визуал", callback_data="expert:image")],
        [InlineKeyboardButton(text="📝 В черновики", callback_data="expert:to_draft")]
    ])

@media_router.message(F.chat.type == "private", F.photo | F.document | F.text)
async def private_gateway(message: Message, state: FSMContext):
    """Шлюз «Приемка — Рабочая группа»: ЛС -> Топик 85"""
    if message.text and message.text.startswith("/"):
        return

    # Игнорируем, если пользователь в квизе
    current_state = await state.get_state()
    if current_state is not None:
        return

    await message.copy_to(
        chat_id=NOTIFICATIONS_CHANNEL_ID,
        message_thread_id=THREAD_ID_DRAFTS,
        reply_markup=get_expert_tools_markup()
    )
    await message.answer("✅ Материал передан в рабочую группу (Топик 85).")

@media_router.message(F.chat.id == NOTIFICATIONS_CHANNEL_ID, F.message_thread_id == THREAD_ID_DRAFTS, F.photo | F.document | F.text)
async def handle_expert_input(message: Message, state: FSMContext):
    """Прием вводных от эксперта прямо в топик (если не переслано ботом)"""
    if message.text and message.text.startswith("/"):
        return

    if message.from_user.is_bot:
        return

    await message.reply("Используйте инструменты ТЕРИОН для подготовки поста:", reply_markup=get_expert_tools_markup())

@media_router.callback_query(F.data == "expert:improve")
async def callback_improve_text(callback: CallbackQuery):
    text = callback.message.text or callback.message.caption or ""
    if not text or "Используйте инструменты" in text or "Материал передан" in text:
         if callback.message.reply_to_message:
             text = callback.message.reply_to_message.text or callback.message.reply_to_message.caption

    if not text:
        await callback.answer("Текст для обработки не найден.")
        return

    await callback.message.answer("🪄 Оформляю пост через RouterAI (DeepSeek)...")
    improved = await router_ai.improve_text(text)

    await callback.message.answer(
        f"✨ <b>Готовый пост:</b>\n\n{improved}",
        parse_mode="HTML",
        reply_markup=get_expert_tools_markup()
    )
    await callback.answer()

@media_router.callback_query(F.data == "expert:image")
async def callback_gen_image(callback: CallbackQuery):
    text = callback.message.text or callback.message.caption or ""
    if not text or "Используйте инструменты" in text or "Материал передан" in text:
         if callback.message.reply_to_message:
             text = callback.message.reply_to_message.text or callback.message.reply_to_message.caption

    prompt = text[:200] if text else "Современная перепланировка"

    await callback.message.answer("🖼 Генерирую визуал через RouterAI (Flux)...")
    img_bytes = await image_gen.generate_image(prompt)

    if img_bytes:
        await callback.message.answer_photo(
            BufferedInputFile(img_bytes, filename="cover.jpg"),
            caption="🖼 Визуал готов! Превратить это в черновик?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📝 Создать черновик", callback_data="expert:to_draft")],
                [InlineKeyboardButton(text="❌ Удалить", callback_data="delete_msg")]
            ])
        )
    else:
        await callback.message.answer("❌ Ошибка генерации визуала.")
    await callback.answer()

@media_router.callback_query(F.data.startswith("expert:to_draft") | (F.data == "expert:publish"))
async def callback_to_draft(callback: CallbackQuery, state: FSMContext = None):
    """Превращение текущего сообщения/фото в официальный черновик ( content_plan )"""
    text = callback.message.text or callback.message.caption or ""
    if "✨ Готовый пост:" in text:
        text = text.replace("✨ Готовый пост:\n\n", "")

    media_list = []
    if callback.message.photo:
        file_id = callback.message.photo[-1].file_id
        media_list.append({"type": "file_id", "data": file_id})

    content_hash = hashlib.md5(text.encode()).hexdigest()

    # Сохраняем в БД
    cursor = await db.conn.execute(
        "INSERT INTO content_plan (type, title, body, cta, content_hash, media_data, publish_date, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("expert_post", "Черновик", text, "Quiz Link", content_hash, json.dumps(media_list), "now", "draft")
    )
    post_id = cursor.lastrowid
    await db.conn.commit()

    await callback.message.answer(
        f"📝 Черновик ID:{post_id} сохранен.",
        reply_markup=get_post_markup(post_id)
    )
    await callback.answer()

@media_router.callback_query(F.data.startswith("expert:improve_draft:"))
async def improve_existing_draft(callback: CallbackQuery):
    post_id = int(callback.data.split(":")[2])
    async with db.conn.execute("SELECT body FROM content_plan WHERE id = ?", (post_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            await callback.answer("❌ Пост не найден.")
            return
        text = row[0]

    await callback.message.answer("🪄 Переоформляю текст черновика...")
    improved = await router_ai.improve_text(text)

    await db.conn.execute("UPDATE content_plan SET body = ? WHERE id = ?", (improved, post_id))
    await db.conn.commit()

    await callback.message.answer(f"✅ Текст черновика {post_id} обновлен:\n\n{improved}", reply_markup=get_post_markup(post_id))
    await callback.answer()

@media_router.callback_query(F.data.startswith("expert:image_for_post:"))
async def gen_image_for_existing_post(callback: CallbackQuery):
    post_id = int(callback.data.split(":")[2])
    async with db.conn.execute("SELECT body, media_data FROM content_plan WHERE id = ?", (post_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            await callback.answer("❌ Пост не найден.")
            return
        text, media_json = row

    await callback.message.answer("🖼 Генерирую визуал (Flux) для поста...")
    img_bytes = await image_gen.generate_image(text[:200])

    if img_bytes:
        image_b64 = base64.b64encode(img_bytes).decode('utf-8')
        media_list = json.loads(media_json) if media_json else []
        media_list.append({"type": "bytes", "data": image_b64})

        await db.conn.execute("UPDATE content_plan SET media_data = ? WHERE id = ?", (json.dumps(media_list), post_id))
        await db.conn.commit()

        await callback.message.answer_photo(
            BufferedInputFile(img_bytes, filename="art.jpg"),
            caption=f"✅ Визуал (Flux) добавлен к черновику {post_id}!",
            reply_markup=get_post_markup(post_id)
        )
    else:
        await callback.message.answer("❌ Ошибка генерации.")
    await callback.answer()

@media_router.callback_query(F.data.startswith(("publish_", "delete_draft:", "delete_msg")))
async def handle_moderation(callback: CallbackQuery):
    if callback.data == "delete_msg":
        await callback.message.delete()
        return

    data_parts = callback.data.split(":")
    action = data_parts[0]
    post_id = data_parts[1]
    post_id = int(post_id)

    async with db.conn.execute("SELECT body, media_data FROM content_plan WHERE id = ?", (post_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            await callback.answer("❌ Пост не найден.")
            return
        text, media_json = row

    if action == "delete_draft":
        await db.conn.execute("DELETE FROM content_plan WHERE id = ?", (post_id,))
        await db.conn.commit()
        await callback.message.edit_text("❌ Черновик удален.")
        return

    # Подготовка медиа
    images_bytes = []
    file_ids = []
    if media_json:
        media_list = json.loads(media_json)
        for item in media_list:
            if item["type"] == "bytes":
                images_bytes.append(base64.b64decode(item["data"]))
            else:
                file_ids.append(item["data"])

    results = []

    # 1. Публикация в Telegram
    if "tg" in action or "all" in action:
        try:
            if not images_bytes and not file_ids:
                await callback.bot.send_message(chat_id=CHANNEL_ID, text=text)
            else:
                media_group = []
                for fid in file_ids:
                    media_group.append(InputMediaPhoto(media=fid, caption=text if not media_group else ""))
                for b in images_bytes:
                    media_group.append(InputMediaPhoto(media=BufferedInputFile(b, filename="image.jpg"), caption=text if not media_group else ""))

                await callback.bot.send_media_group(chat_id=CHANNEL_ID, media=media_group[:10])
            results.append("TG ✅")
        except Exception as e:
            results.append(f"TG ❌ ({e})")

    # 2. Публикация в VK
    if "vk" in action or "all" in action:
        try:
            attachment_ids = []
            if images_bytes:
                attachment_ids.extend(await vk_service.upload_photos(images_bytes))

            vk_text = text
            if "#терион" not in vk_text.lower():
                vk_text += f"\n\n#терион #перепланировка\nУслуги ТЕРИОН: {MINI_APP_URL}"

            success = await vk_service.send_to_community(message=vk_text, attachments=attachment_ids)
            results.append("VK ✅" if success else "VK ❌")
        except Exception as e:
            results.append(f"VK ❌ ({e})")

    # Обновляем статус в БД
    await db.conn.execute("UPDATE content_plan SET status = 'published', published_at = CURRENT_TIMESTAMP WHERE id = ?", (post_id,))
    await db.conn.commit()

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"Результат публикации поста {post_id}: {', '.join(results)}")
    await callback.answer("Процесс завершен")
