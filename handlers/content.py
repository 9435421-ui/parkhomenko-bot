import os
import io
import hashlib
import base64
import fitz  # PyMuPDF
from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, BufferedInputFile, InputMediaPhoto
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from config import (
    THREAD_ID_DRAFTS, OPENROUTER_API_KEY, CHANNEL_ID,
    ADMIN_ID, LEADS_GROUP_CHAT_ID, BOT_TOKEN
)
from services.vk_service import vk_service
from services.yandex_art import yandex_art
from database.db import db
import aiohttp
import json

router = Router()

class ContentCreation(StatesGroup):
    waiting_for_media = State()

def get_post_markup(post_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Опубликовать везде", callback_data=f"publish_all:{post_id}")],
        [InlineKeyboardButton(text="📢 Только в TG", callback_data=f"publish_tg:{post_id}")],
        [InlineKeyboardButton(text="💙 Только в VK", callback_data=f"publish_vk:{post_id}")],
        [InlineKeyboardButton(text="🎨 Создать обложку AI", callback_data=f"gen_art:{post_id}")],
        [InlineKeyboardButton(text="❌ Удалить", callback_data=f"delete_draft:{post_id}")]
    ])

@router.message(F.message_thread_id == THREAD_ID_DRAFTS, F.photo | F.document | F.text)
async def handle_expert_input(message: Message, state: FSMContext):
    """Прием вводных от эксперта: файлы + текст"""
    if message.text and message.text.startswith("/"):
        return

    # Собираем данные
    caption = message.caption or message.text or "Перепланировка"
    raw_images = [] # Список bytes или file_id

    # Обработка фото
    if message.photo:
        raw_images.append(message.photo[-1].file_id)

    # Обработка PDF
    if message.document and message.document.mime_type == "application/pdf":
        await message.answer("🔄 Конвертирую PDF в изображения...")
        file_path = await message.bot.get_file(message.document.file_id)

        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path.file_path}") as resp:
                pdf_data = await resp.read()

        # Конвертация
        pdf_doc = fitz.open(stream=pdf_data, filetype="pdf")
        for page in pdf_doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            raw_images.append(pix.tobytes("jpg"))
        pdf_doc.close()

    await message.answer("🤖 Генерирую профессиональный текст и черновик...")

    # Генерация текста через AI
    prompt = f"""
    Ты — эксперт по перепланировкам в компании 'Право и Решение'.
    Напиши пост для соцсетей на основе следующих фактов: {caption}

    Требования:
    1. Стиль: профессиональный, экспертный, но понятный.
    2. Добавь тематические хэштеги: #перепланировка #правоирешение #москва.
    3. В конце обязательно добавь призыв пройти квиз для оценки проекта.
    4. Упомяни бота @{(await message.bot.get_me()).username}.
    5. ЗАПРЕЩЕНО использовать лишний текст на картинках.
    """

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            json={
                "model": "openai/gpt-3.5-turbo",
                "messages": [{"role": "user", "content": prompt}]
            }
        ) as resp:
            result = await resp.json()
            ai_text = result['choices'][0]['message']['content']

    # Подготовка медиа для БД (JSON с base64 для байтов)
    media_list = []
    for img in raw_images:
        if isinstance(img, bytes):
            media_list.append({"type": "bytes", "data": base64.b64encode(img).decode()})
        else:
            media_list.append({"type": "file_id", "data": img})

    media_json = json.dumps(media_list)
    content_hash = hashlib.md5(ai_text.encode()).hexdigest()

    # Проверка на дубли
    async with db.conn.execute("SELECT id FROM content_plan WHERE content_hash = ?", (content_hash,)) as cursor:
        if await cursor.fetchone():
            await message.answer("⚠️ Похожий пост уже был создан ранее.")
            return

    # Сохраняем в БД
    cursor = await db.conn.execute(
        "INSERT INTO content_plan (type, title, body, cta, content_hash, media_data, publish_date, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("expert_post", "Черновик", ai_text, "Quiz Link", content_hash, media_json, "now", "draft")
    )
    post_id = cursor.lastrowid
    await db.conn.commit()

    # Отправляем медиа в группу для предпросмотра
    if raw_images:
        preview = raw_images[0]
        if isinstance(preview, str):
            await message.bot.send_photo(chat_id=LEADS_GROUP_CHAT_ID, photo=preview, message_thread_id=THREAD_ID_DRAFTS)
        else:
            await message.bot.send_photo(
                chat_id=LEADS_GROUP_CHAT_ID,
                photo=BufferedInputFile(preview, filename="preview.jpg"),
                message_thread_id=THREAD_ID_DRAFTS
            )

    # Отправляем в группу на модерацию
    await message.bot.send_message(
        chat_id=LEADS_GROUP_CHAT_ID,
        text=f"📝 <b>ПРЕДПРОСМОТР ПОСТА (ID: {post_id}):</b>\n\n{ai_text}",
        message_thread_id=THREAD_ID_DRAFTS,
        parse_mode="HTML",
        reply_markup=get_post_markup(post_id)
    )

@router.callback_query(F.data.startswith("gen_art:"))
async def generate_art_for_post(callback: CallbackQuery):
    post_id = int(callback.data.split(":")[1])
    async with db.conn.execute("SELECT body, media_data FROM content_plan WHERE id = ?", (post_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            await callback.answer("❌ Пост не найден.")
            return
        text, media_json = row

    await callback.message.answer("🎨 Генерирую иллюстрацию через Yandex Art...")

    prompt = f"Иллюстрация для статьи о перепланировке: {text[:100]}"
    image_data = await yandex_art.generate_image(prompt)

    if image_data:
        media_list = json.loads(media_json) if media_json else []
        media_list.append({"type": "bytes", "data": image_data})
        await db.conn.execute("UPDATE content_plan SET media_data = ? WHERE id = ?", (json.dumps(media_list), post_id))
        await db.conn.commit()

        await callback.message.answer_photo(
            BufferedInputFile(base64.b64decode(image_data), filename="art.jpg"),
            caption="✅ Обложка сгенерирована и добавлена к черновику!"
        )
    else:
        await callback.message.answer("❌ Ошибка генерации.")
    await callback.answer()

@router.callback_query(F.data.startswith(("publish_", "delete_draft:")))
async def handle_moderation(callback: CallbackQuery):
    data_parts = callback.data.split(":")
    action = data_parts[0]
    post_id = data_parts[1]
    post_id = int(post_id)

    async with db.conn.execute("SELECT body, media_data FROM content_plan WHERE id = ?", (post_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            await callback.answer("❌ Пост не найден в базе.")
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
                # Формируем медиагруппу
                media_group = []
                # Сначала file_ids
                for fid in file_ids:
                    media_group.append(InputMediaPhoto(media=fid, caption=text if not media_group else ""))
                # Затем байты
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

            # Внимание: для VK если фото в TG по file_id, их нужно сначала скачать.
            # Для упрощения V2.1 пока грузим только те, что были байтами (из PDF).

            success = await vk_service.send_to_community(message=text, attachments=attachment_ids)
            results.append("VK ✅" if success else "VK ❌")
        except Exception as e:
            results.append(f"VK ❌ ({e})")

    # Обновляем статус в БД
    await db.conn.execute("UPDATE content_plan SET status = 'published', published_at = CURRENT_TIMESTAMP WHERE id = ?", (post_id,))
    await db.conn.commit()

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(f"Результат публикации поста {post_id}: {', '.join(results)}")
    await callback.answer("Процесс завершен")
