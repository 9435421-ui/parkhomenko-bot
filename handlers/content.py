"""
Content Handler — TERION Ecosystem (RouterAI + YandexART Edition)
TG + VK публикация, AI-генерация контента, квиз-интеграция
"""
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, KeyboardButton, FSInputFile,
    InputMediaPhoto, BufferedInputFile,
)
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging
import aiohttp
import json
import base64
import os
import tempfile
import io
import asyncio
import re
import time
from datetime import datetime, timedelta
from typing import Optional

# Кэш шаблонов: 5 минут, чтобы не читать диск при каждом сообщении
_TEMPLATE_CACHE_TTL = 300  # секунд
_template_cache: dict = {}
from PIL import Image
import io

from database.db import db
from handlers.vk_publisher import VKPublisher
from agents.content_agent import ContentAgent
from config import (
    CONTENT_BOT_TOKEN,
    BOT_TOKEN,
    CHANNEL_ID_TERION,
    CHANNEL_ID_DOM_GRAD,
    LEADS_GROUP_CHAT_ID,
    THREAD_ID_DRAFTS,
    THREAD_ID_CONTENT_PLAN,
    THREAD_ID_TRENDS_SEASON,
    THREAD_ID_LOGS,
    ROUTER_AI_KEY,
    YANDEX_API_KEY,
    FOLDER_ID,
    MAX_API_KEY,
    YANDEX_ART_ENABLED,
    VK_TOKEN,
    VK_GROUP_ID,
    VK_QUIZ_LINK,
    CHANNEL_NAMES,
    CONTENT_HASHTAGS,
    POSTS_PER_DAY_LIMIT
)

logger = logging.getLogger(__name__)
content_router = Router()

# Папка шаблонов контента (редактируемые Юлией без правки кода)
_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "content")


def _load_content_template(filename: str, default: str) -> str:
    """Читает шаблон из templates/content/ с кэшем 5 мин; при ошибке возвращает default."""
    now = time.time()
    if filename in _template_cache:
        content, expiry = _template_cache[filename]
        if now < expiry:
            return content
    path = os.path.join(_TEMPLATES_DIR, filename)
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            _template_cache[filename] = (content, now + _TEMPLATE_CACHE_TTL)
            return content
        logger.warning(f"⚠️ Template {filename} not found, using default")
    except Exception as e:
        logger.warning(f"⚠️ Template {filename} not found, using default — {e}")
    return default


def _get_expert_signature() -> str:
    """Подпись эксперта для постов (из signature.txt или дефолт)."""
    default = "\n\n---\n🏡 Эксперт: Юлия Пархоменко\nКомпания: TERION"
    return _load_content_template("signature.txt", default).rstrip("\n") or default


def _markdown_bold_to_html(text: str) -> str:
    """Конвертирует **жирный** в <b>жирный</b> для Telegram HTML."""
    if not text:
        return text
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)


def ensure_quiz_and_hashtags(text: str) -> str:
    """Добавляет в пост ссылку на квиз и обязательные хэштеги; конвертирует ** в <b>."""
    if not text or not text.strip():
        return text
    out = _markdown_bold_to_html(text.rstrip())
    if VK_QUIZ_LINK not in out:
        out += f"\n\n📍 <a href='{VK_QUIZ_LINK}'>Пройти квиз</a>"
    if CONTENT_HASHTAGS and CONTENT_HASHTAGS.strip():
        hashtag_line = CONTENT_HASHTAGS.strip()
        if hashtag_line not in out:
            out += f"\n\n{hashtag_line}"
    return out

# Инициализация VK
vk_publisher = VKPublisher(VK_TOKEN, int(VK_GROUP_ID))


# === FSM STATES ===
class ContentStates(StatesGroup):
    main_menu = State()
    photo_topic = State()      # Тема перед загрузкой фото
    photo_upload = State()     # Загрузка фото
    preview_mode = State()          # Режим превью перед публикацией
    series_days = State()
    series_topic = State()
    ai_visual_prompt = State()  # Ввод промпта после выбора модели
    news_topic = State()
    ai_plan = State()          # Интерактивный план (дни + тема)
    quick_text = State()
    holiday_rf = State()       # Поздравление с официальным праздником РФ
    ai_text = State()
    ai_series = State()
    ai_visual_select = State()
    ai_news = State()
    ai_news_choose = State()
    ai_fact_choose = State()
    edit_post = State()


# === AI CLIENTS ===
from services.image_generator import image_generator
from utils.router_ai import router_ai

async def _auto_generate_image(prompt: str) -> Optional[bytes]:
    """Автоматический выбор модели генерации изображения."""
    return await image_generator.generate_image(prompt)


# === KEYBOARDS ===

def get_main_menu() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="📸 Фото → Описание → Пост")],
        [KeyboardButton(text="🎨 ИИ-Визуал"), KeyboardButton(text="✨ Креатив")],
        [KeyboardButton(text="📰 Новость"), KeyboardButton(text="📋 План")],
        [KeyboardButton(text="📝 Быстрый текст"), KeyboardButton(text="💡 Интересный факт")],
        [KeyboardButton(text="🎉 Праздник РФ")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_preview_keyboard(post_id: int, has_image: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📤 Во все каналы", callback_data=f"pub_all:{post_id}")
    builder.button(text="🚀 TERION", callback_data=f"pub_terion:{post_id}")
    builder.button(text="🏘 ДОМ ГРАНД", callback_data=f"pub_dom_grnd:{post_id}")
    builder.button(text="📱 MAX", callback_data=f"pub_max:{post_id}")
    builder.button(text="🌐 VK", callback_data=f"pub_vk:{post_id}")
    builder.button(text="🗑 В черновики", callback_data=f"draft:{post_id}")
    builder.button(text="✏️ Редактировать", callback_data=f"edit:{post_id}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1, 2, 2, 1, 1, 1)
    return builder.as_markup()


def get_queue_keyboard(post_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📤 Во все каналы", callback_data=f"pub_all:{post_id}")
    builder.button(text="🚀 TERION", callback_data=f"pub_terion:{post_id}")
    builder.button(text="🏘 ДОМ ГРАНД", callback_data=f"pub_dom_grnd:{post_id}")
    builder.button(text="📱 MAX", callback_data=f"pub_max:{post_id}")
    builder.button(text="🌐 VK", callback_data=f"pub_vk:{post_id}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1, 2, 2, 1)
    return builder.as_markup()


def get_back_btn() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data="back_menu")
    return builder.as_markup()


# === HELPERS ===

async def download_photo(bot: Bot, file_id: str) -> Optional[bytes]:
    try:
        if file_id.startswith("http"):
            async with aiohttp.ClientSession() as session:
                async with session.get(file_id) as resp:
                    if resp.status == 200:
                        return await resp.read()
                    return None
        file = await bot.get_file(file_id)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            await bot.download_file(file.file_path, tmp.name)
            with open(tmp.name, "rb") as f:
                data = f.read()
            os.unlink(tmp.name)
            return data
    except Exception as e:
        logger.error(f"Download error: {e}")
    return None


async def compress_image(image_bytes: bytes, max_size: int = 1024, quality: int = 85) -> bytes:
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.error(f"Compression error: {e}")
        return image_bytes


def _build_cover_prompt(text: str) -> str:
    clean = re.sub(r"<[^>]+>", "", text).lower()
    parts = []
    if any(w in clean for w in ["перепланировк", "снос стен", "объединени"]):
        parts.append("apartment renovation, open space planning")
    if any(w in clean for w in ["кухн", "гостин"]):
        parts.append("kitchen living room studio")
    base = ", ".join(parts) if parts else "modern Moscow apartment interior"
    return f"Professional real estate photography, {base}, high quality, realistic, 4K. No text."


async def show_preview(message: Message, text: str, image_file_id: Optional[str] = None, post_id: Optional[int] = None):
    if not post_id:
        post_id = await db.add_content_post(
            title="Preview", body=text, cta="", image_url=image_file_id,
            channel="preview", status="preview"
        )
    caption = f"👁 <b>Предпросмотр</b>\n\n{text[:700]}{'...' if len(text) > 700 else ''}"
    if not image_file_id:
        prompt = _build_cover_prompt(text)
        image_b64 = await _auto_generate_image(prompt)
        if image_b64:
            try:
                image_bytes = base64.b64decode(image_b64)
                photo_input = BufferedInputFile(image_bytes, filename="cover.jpg")
                sent = await message.answer_photo(
                    photo=photo_input, caption=caption,
                    reply_markup=get_preview_keyboard(post_id, True), parse_mode="HTML"
                )
                if sent.photo:
                    await db.update_content_post(post_id, image_url=sent.photo[-1].file_id)
                return post_id
            except Exception:
                pass
    kb = get_preview_keyboard(post_id, bool(image_file_id))
    if image_file_id:
        await message.answer_photo(photo=image_file_id, caption=caption, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(caption, reply_markup=kb, parse_mode="HTML")
    return post_id


# === HANDLERS ===

@content_router.message(F.text.in_([
    "📸 Фото → Описание → Пост", "🎨 ИИ-Визуал", "✨ Креатив",
    "📰 Новость", "📋 План", "📝 Быстрый текст",
    "💡 Интересный факт", "🎉 Праздник РФ"
]))
async def global_menu_handler(message: Message, state: FSMContext):
    await state.clear()
    text = message.text
    if text == "📸 Фото → Описание → Пост":
        await photo_start(message, state)
    elif text == "🎨 ИИ-Визуал":
        await visual_select_model(message, state)
    elif text == "✨ Креатив":
        await series_start(message, state)
    elif text == "📰 Новость":
        await news_start(message, state)
    elif text == "📋 План":
        await plan_start(message, state)
    elif text == "📝 Быстрый текст":
        await quick_start(message, state)
    elif text == "💡 Интересный факт":
        await fact_start(message, state)
    elif text == "🎉 Праздник РФ":
        await holiday_rf_start(message, state)


async def photo_start(message: Message, state: FSMContext):
    await message.answer("📸 <b>Шаг 1/2: Введите тему поста:</b>", reply_markup=get_back_btn(), parse_mode="HTML")
    await state.set_state(ContentStates.photo_topic)

@content_router.message(ContentStates.photo_topic)
async def process_photo_topic(message: Message, state: FSMContext):
    await state.update_data(photo_topic=message.text)
    await message.answer("📸 <b>Шаг 2/2: Загрузите фото:</b>", parse_mode="HTML")
    await state.set_state(ContentStates.photo_upload)

@content_router.message(ContentStates.photo_upload, F.photo)
async def process_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    topic = data.get('photo_topic', 'Перепланировка')
    photo = message.photo[-1]
    await message.answer("🔍 <b>Анализирую фото...</b>", parse_mode="HTML")
    image_bytes = await download_photo(message.bot, photo.file_id)
    if not image_bytes:
        return await message.answer("❌ Ошибка загрузки")
    compressed = await compress_image(image_bytes)
    image_b64 = base64.b64encode(compressed).decode()
    prompt = f"Ты эксперт TERION. Тема: {topic}. Проанализируй фото и напиши пост (400-700 знаков)."
    description = await router_ai.analyze_image(image_b64, prompt)
    if not description:
        description = f"<b>Перепланировка: {topic}</b>\n\nСогласование в МЖИ и техзаключение."
    description = ensure_quiz_and_hashtags(description)
    post_id = await db.add_content_post(
        title=f"Фото: {topic[:40]}", body=description, cta="",
        image_url=photo.file_id, channel="photo", status="preview"
    )
    await message.answer_photo(
        photo=photo.file_id, caption=f"👁 <b>Превью</b>\n\n{description[:700]}",
        reply_markup=get_preview_keyboard(post_id, True), parse_mode="HTML"
    )
    await state.set_state(ContentStates.preview_mode)

async def visual_select_model(message: Message, state: FSMContext):
    await message.answer("🎨 <b>Введите описание сцены:</b>", reply_markup=get_back_btn(), parse_mode="HTML")
    await state.set_state(ContentStates.ai_visual_prompt)

@content_router.message(ContentStates.ai_visual_prompt)
async def ai_visual_handler(message: Message, state: FSMContext):
    await message.answer("⏳ <b>Генерирую...</b>", parse_mode="HTML")
    image_b64 = await _auto_generate_image(message.text)
    if not image_b64:
        return await message.answer("❌ Ошибка генерации")
    image_bytes = base64.b64decode(image_b64)
    photo = BufferedInputFile(image_bytes, filename="visual.jpg")
    sent = await message.answer_photo(
        photo=photo, caption=f"✅ Готово: {message.text[:50]}",
        reply_markup=InlineKeyboardBuilder()
        .button(text="📝 Создать пост", callback_data=f"art_to_post:{message.text[:28]}")
        .button(text="◀️ Меню", callback_data="back_menu").as_markup(),
        parse_mode="HTML"
    )
    if sent.photo:
        await state.update_data(visual_file_id=sent.photo[-1].file_id, visual_prompt=message.text)

@content_router.callback_query(F.data.startswith("art_to_post:"))
async def art_to_post_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    topic = data.get("visual_prompt", "Перепланировка")
    await callback.message.answer("✍️ <b>Пишу пост...</b>", parse_mode="HTML")
    prompt = f"Напиши экспертный пост TERION на тему: {topic}."
    text = await router_ai.generate_response(user_prompt=prompt)
    if not text:
        text = f"<b>{topic}</b>\n\nЭкспертный подход к перепланировке."
    text = ensure_quiz_and_hashtags(text)
    await show_preview(callback.message, text, image_file_id=data.get("visual_file_id"))
    await state.set_state(ContentStates.preview_mode)

async def series_start(message: Message, state: FSMContext):
    await message.answer("✨ <b>Введите: дней, тема</b> (напр. 7, студия):", reply_markup=get_back_btn(), parse_mode="HTML")
    await state.set_state(ContentStates.ai_series)

@content_router.message(ContentStates.ai_series)
async def ai_series_handler(message: Message, state: FSMContext):
    try:
        days, topic = [p.strip() for p in message.text.split(',', 1)]
        days = int(days)
    except:
        return await message.answer("❌ Формат: число, тема")
    await message.answer(f"⏳ <b>Генерирую {days} постов...</b>", parse_mode="HTML")
    prompt = f"Создай серию из {days} постов для прогрева по теме {topic}."
    result = await router_ai.generate_response(user_prompt=prompt)
    post_id = await db.add_content_post(title=f"Серия: {topic}", body=result or "Ошибка", channel="series", status="draft")
    await message.bot.send_message(LEADS_GROUP_CHAT_ID, f"📅 <b>Серия {days} дней: {topic}</b>\n\n{result}", message_thread_id=THREAD_ID_DRAFTS, reply_markup=get_queue_keyboard(post_id))
    await message.answer("✅ Серия готова и отправлена в черновики.")

async def news_start(message: Message, state: FSMContext):
    await message.answer("📰 <b>Введите тему новости:</b>", reply_markup=get_back_btn(), parse_mode="HTML")
    await state.set_state(ContentStates.ai_news)

@content_router.message(ContentStates.ai_news)
async def ai_news_handler(message: Message, state: FSMContext):
    await message.answer("🔍 <b>Пишу новость...</b>", parse_mode="HTML")
    prompt = f"Напиши новостной пост TERION на тему: {message.text}."
    news = await router_ai.generate_response(user_prompt=prompt)
    post_id = await show_preview(message, news or "Ошибка")
    await state.set_state(ContentStates.preview_mode)

async def plan_start(message: Message, state: FSMContext):
    await message.answer("📋 <b>Введите: дней, тема:</b>", reply_markup=get_back_btn(), parse_mode="HTML")
    await state.set_state(ContentStates.ai_plan)

@content_router.message(ContentStates.ai_plan)
async def ai_plan_handler(message: Message, state: FSMContext):
    try:
        days, topic = [p.strip() for p in message.text.split(',', 1)]
    except:
        return await message.answer("❌ Формат: дни, тема")
    await message.answer(f"⏳ <b>Составляю план на {days} дней...</b>", parse_mode="HTML")
    prompt = f"Составь контент-план на {days} дней по теме {topic}."
    plan = await router_ai.generate_response(user_prompt=prompt)
    await message.bot.send_message(LEADS_GROUP_CHAT_ID, f"📋 <b>План: {topic}</b>\n\n{plan}", message_thread_id=THREAD_ID_CONTENT_PLAN)
    await message.answer("✅ План готов и отправлен в топик 83.")

async def quick_start(message: Message, state: FSMContext):
    await message.answer("📝 <b>Введите тему:</b>", reply_markup=get_back_btn(), parse_mode="HTML")
    await state.set_state(ContentStates.ai_text)

@content_router.message(ContentStates.ai_text)
async def ai_text_handler(message: Message, state: FSMContext):
    await message.answer("⏳ <b>Пишу...</b>", parse_mode="HTML")
    prompt = f"Напиши экспертный пост TERION на тему: {message.text}."
    text = await router_ai.generate_response(user_prompt=prompt)
    await show_preview(message, text or "Ошибка")
    await state.set_state(ContentStates.preview_mode)

async def fact_start(message: Message, state: FSMContext):
    await message.answer("💡 <b>Введите тему факта:</b>", reply_markup=get_back_btn(), parse_mode="HTML")
    await state.set_state(ContentStates.ai_text) # Используем ai_text для простоты

async def holiday_rf_start(message: Message, state: FSMContext):
    await message.answer("🎉 <b>Введите название праздника:</b>", reply_markup=get_back_btn(), parse_mode="HTML")
    await state.set_state(ContentStates.holiday_rf)

@content_router.message(ContentStates.holiday_rf)
async def holiday_rf_handler(message: Message, state: FSMContext):
    await message.answer("⏳ <b>Пишу поздравление...</b>", parse_mode="HTML")
    prompt = f"Напиши праздничный пост TERION: {message.text}."
    body = await router_ai.generate_response(user_prompt=prompt)
    await show_preview(message, body or "Ошибка")
    await state.set_state(ContentStates.preview_mode)


# === ПУБЛИКАЦИЯ ===

@content_router.callback_query(F.data.startswith("pub_vk:"))
async def publish_vk_only(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    text = post['body'] # В ВК можно без HTML
    try:
        image_bytes = await download_photo(callback.bot, post["image_url"]) if post.get("image_url") else None
        vk_id = await vk_publisher.post_with_photo(text, image_bytes) if image_bytes else await vk_publisher.post_text_only(text)
        await db.mark_as_published(post_id)
        await callback.message.edit_text(f"✅ Опубликовано в VK: wall-{VK_GROUP_ID}_{vk_id}", reply_markup=get_back_btn())
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}", reply_markup=get_back_btn())
    await state.clear()

@content_router.callback_query(F.data.startswith("pub_all:"))
async def publish_all(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    from services.publisher import publisher
    text = ensure_quiz_and_hashtags(post['body'])
    image_bytes = await download_photo(callback.bot, post["image_url"]) if post.get("image_url") else None
    await publisher.publish_all(text, image_bytes, post_id=post_id)
    await callback.message.edit_text("✅ Опубликовано везде!", reply_markup=get_back_btn())
    await state.clear()

@content_router.callback_query(F.data.startswith("draft:"))
async def save_draft(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    await callback.bot.send_message(LEADS_GROUP_CHAT_ID, f"📝 <b>Черновик #{post_id}</b>\n\n{post['body']}", message_thread_id=THREAD_ID_DRAFTS, reply_markup=get_queue_keyboard(post_id))
    await db.update_content_post(post_id, status="in_drafts")
    await callback.message.edit_text("✅ В черновиках", reply_markup=get_back_btn())
    await state.clear()

@content_router.callback_query(F.data == "cancel")
async def cancel_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Отменено", reply_markup=get_back_btn())

@content_router.callback_query(F.data == "back_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🎯 <b>TERION Content Bot</b>", reply_markup=get_main_menu(), parse_mode="HTML")

@content_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🎯 <b>TERION Content Bot</b>", reply_markup=get_main_menu(), parse_mode="HTML")
    await state.set_state(ContentStates.main_menu)

def register_handlers(dp):
    dp.include_router(content_router)
