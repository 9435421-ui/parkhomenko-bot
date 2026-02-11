"""
Content Handler — TERION Content Bot (TG + VK Edition)
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging, aiohttp, json, base64, os, tempfile
from datetime import datetime, timedelta
from typing import Optional
from database import db
from handlers.vk_publisher import VKPublisher
from config import TERION_CHANNEL_ID, DOM_GRAND_CHANNEL_ID, LEADS_GROUP_CHAT_ID, THREAD_ID_DRAFTS, THREAD_ID_CONTENT_PLAN, THREAD_ID_LOGS, ROUTER_AI_KEY, YANDEX_API_KEY, FOLDER_ID, VK_TOKEN, VK_GROUP_ID, VK_QUIZ_LINK

logger = logging.getLogger(__name__)
content_router = Router()
vk_publisher = VKPublisher(VK_TOKEN, int(VK_GROUP_ID))

class ContentStates(StatesGroup):
    main_menu = State()
    photo_upload = State()
    ai_text = State()
    preview_mode = State()
    series_days = State()
    series_topic = State()
    visual_prompt = State()
    news_topic = State()
    plan_days = State()
    quick_text = State()
    edit_post = State()

class YandexArtClient:
    def __init__(self, api_key: str, folder_id: str):
        self.api_key = api_key
        self.folder_id = folder_id
        self.headers = {"Authorization": f"Api-Key {api_key}", "Content-Type": "application/json"}
    
    async def generate(self, prompt: str) -> Optional[str]:
        payload = {"modelUri": f"art://{self.folder_id}/yandex-art/latest", "messages": [{"weight": 1, "text": prompt}], "generationOptions": {"seed": int(datetime.now().timestamp()), "aspectRatio": {"widthRatio": 16, "heightRatio": 9}}}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post("https://llm.api.cloud.yandex.net/foundationModels/v1/imageGeneration", headers=self.headers, json=payload) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    op_id = data.get("id")
                    if not op_id:
                        return None
                    for _ in range(30):
                        await asyncio.sleep(2)
                        async with session.get(f"https://operation.api.cloud.yandex.net/operations/{op_id}", headers=self.headers) as check:
                            if check.status == 200:
                                result = await check.json()
                                if result.get("done"):
                                    return result.get("response", {}).get("image")
        except Exception as e:
            logger.error(f"YandexART error: {e}")
        return None

class RouterAIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    async def generate(self, prompt: str, model: str = "quin", max_tokens: int = 2000) -> Optional[str]:
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 0.7}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post("https://routerai.ru/api/v1/chat/completions", headers=self.headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"RouterAI error: {e}")
        return None
    
    async def analyze_image(self, image_b64: str, prompt: str) -> Optional[str]:
        payload = {"model": "gemini-2.5-flash-image", "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}]}], "max_tokens": 1000}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post("https://routerai.ru/api/v1/chat/completions", headers=self.headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Vision error: {e}")
        return None

yandex_art = YandexArtClient(YANDEX_API_KEY, FOLDER_ID)
router_ai = RouterAIClient(ROUTER_AI_KEY)
import asyncio
from PIL import Image
import io

def get_main_menu() -> ReplyKeyboardMarkup:
    kb = [[KeyboardButton(text="📸 Фото → Описание → Пост")], [KeyboardButton(text="🎨 Яндекс АРТ"), KeyboardButton(text="📅 Серия постов")], [KeyboardButton(text="📰 Новость"), KeyboardButton(text="📋 Контент-план")], [KeyboardButton(text="📝 Быстрый текст")]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_preview_keyboard(post_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Опубликовать везде", callback_data=f"pub_all:{post_id}")
    builder.button(text="📱 Только TG", callback_data=f"pub_tg:{post_id}")
    builder.button(text="🌐 Только VK", callback_data=f"pub_vk:{post_id}")
    builder.button(text="🗑 В черновики", callback_data=f"draft:{post_id}")
    builder.button(text="✏️ Редактировать", callback_data=f"edit:{post_id}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1, 2, 2, 1)
    return builder.as_markup()

def get_back_btn() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data="back_menu")
    return builder.as_markup()

async def download_photo(bot: Bot, file_id: str) -> Optional[bytes]:
    try:
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
    """Сжатие изображения для экономии токенов"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ('RGBA', 'P', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            if img.mode in ('RGBA', 'LA'):
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            else:
                img = img.convert('RGB')
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            logger.info(f"Image resized: {img.size}")
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        compressed = output.getvalue()
        original_kb = len(image_bytes) / 1024
        compressed_kb = len(compressed) / 1024
        savings = (1 - len(compressed) / len(image_bytes)) * 100
        logger.info(f"Image compressed: {original_kb:.1f}KB → {compressed_kb:.1f}KB ({savings:.0f}% saved)")
        return compressed
    except Exception as e:
        logger.error(f"Compression error: {e}")
        return image_bytes

async def show_preview(message: Message, text: str, image_file_id: Optional[str] = None, post_id: Optional[int] = None):
    if not post_id:
        post_id = await db.add_content_post(title="Preview", body=text, image_url=image_file_id, channel="preview", status="preview")
    kb = get_preview_keyboard(post_id)
    if image_file_id:
        await message.answer_photo(photo=image_file_id, caption=f"👁 <b>Предпросмотр</b>\n\n{text}\n\n<i>Выберите действие:</i>", reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(f"👁 <b>Предпросмотр</b>\n\n{text}\n\n<i>Выберите действие:</i>", reply_markup=kb, parse_mode="HTML")
    return post_id

@content_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🎯 <b>TERION Content Bot</b>\n\nСоздание и публикация контента:\n• Telegram (TERION + ДОМ ГРАНД)\n• ВКонтакте (с кнопками)\n\nВыберите действие:", reply_markup=get_main_menu(), parse_mode="HTML")
    await state.set_state(ContentStates.main_menu)

@content_router.message(F.text == "📸 Фото → Описание → Пост")
async def photo_start(message: Message, state: FSMContext):
    await message.answer("📸 <b>Фото → Описание → Пост</b>\n\n1. Загрузите фото\n2. AI создаст описание\n3. Предпросмотр и публикация\n\n<b>Отправьте фото:</b>", reply_markup=get_back_btn(), parse_mode="HTML")
    await state.set_state(ContentStates.photo_upload)

@content_router.message(ContentStates.photo_upload, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file_id = photo.file_id
    image_bytes = await download_photo(message.bot, file_id)
    if not image_bytes:
        await message.answer("❌ Ошибка загрузки фото", reply_markup=get_main_menu())
        await state.clear()
        return
    await message.answer("🗜 <b>Сжимаю фото...</b>", parse_mode="HTML")
    compressed_bytes = await compress_image(image_bytes, max_size=1024, quality=85)
    await message.answer("🔍 <b>Анализирую фото...</b>", parse_mode="HTML")
    image_b64 = base64.b64encode(compressed_bytes).decode()
    prompt = "Ты — эксперт по перепланировкам. Опиши фото интерьера для поста. 150-200 слов. Добавь призыв к консультации @terion_bot"
    description = await router_ai.analyze_image(image_b64, prompt)
    if not description:
        description = "📸 Экспертный анализ объекта.\n\n👉 Консультация: @terion_bot"
    post_id = await show_preview(message, description, file_id)
    await state.set_state(ContentStates.preview_mode)
    await state.update_data(post_id=post_id, description=description, file_id=file_id, image_bytes=compressed_bytes)

@content_router.message(F.text == "🎨 Яндекс АРТ")
async def art_start(message: Message, state: FSMContext):
    await message.answer("🎨 <b>Яндекс АРТ</b>\n\nВведите описание:", reply_markup=get_back_btn(), parse_mode="HTML")
    await state.set_state(ContentStates.visual_prompt)

@content_router.message(ContentStates.visual_prompt)
async def generate_art(message: Message, state: FSMContext):
    prompt = message.text
    await message.answer("⏳ <b>Генерация (10-30 сек)...</b>", parse_mode="HTML")
    enhanced = f"{prompt}, professional interior photography, high quality, detailed, no text, no watermarks"
    image_b64 = await yandex_art.generate(enhanced)
    if not image_b64:
        await message.answer("❌ Ошибка генерации", reply_markup=get_main_menu())
        await state.clear()
        return
    image_bytes = base64.b64decode(image_b64)
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name
    await message.answer_photo(photo=FSInputFile(tmp_path), caption=f"✅ <b>Готово!</b>\n\n<code>{prompt}</code>", reply_markup=InlineKeyboardBuilder().button(text="💾 Использовать в посте", callback_data=f"use_art:{prompt}").button(text="🔄 Еще вариант", callback_data="regen_art").button(text="◀️ Меню", callback_data="back_menu").as_markup(), parse_mode="HTML")
    os.unlink(tmp_path)
    await state.clear()

@content_router.callback_query(F.data.startswith("use_art:"))
async def use_generated_art(callback: CallbackQuery, state: FSMContext):
    prompt = callback.data.split(":", 1)[1]
    await callback.answer("Добавьте текст к посту")
    await callback.message.answer(f"📝 <b>Создание поста с изображением</b>\n\nВведите текст поста:", reply_markup=get_back_btn(), parse_mode="HTML")
    await state.set_state(ContentStates.quick_text)
    await state.update_data(art_prompt=prompt, has_image=True)

@content_router.message(F.text == "📅 Серия постов")
async def series_start(message: Message, state: FSMContext):
    await message.answer("📅 <b>Серия постов</b>\n\nСколько дней? (1-60):", reply_markup=get_back_btn(), parse_mode="HTML")
    await state.set_state(ContentStates.series_days)

@content_router.message(ContentStates.series_days)
async def series_days_input(message: Message, state: FSMContext):
    try:
        days = int(message.text)
        if days < 1 or days > 60:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите число от 1 до 60")
        return
    await state.update_data(days=days)
    await message.answer(f"✅ <b>{days} дней</b>\n\nВведите тему серии:", parse_mode="HTML")
    await state.set_state(ContentStates.series_topic)

@content_router.message(ContentStates.series_topic)
async def generate_series(message: Message, state: FSMContext):
    data = await state.get_data()
    days = data.get("days", 7)
    topic = message.text
    await message.answer(f"⏳ <b>Генерирую {days} постов...</b>", parse_mode="HTML")
    prompt = f"Создай {days} постов для прогрева по теме «{topic}». JSON массив с полями day, title, text."
    result = await router_ai.generate(prompt, max_tokens=4000)
    if not result:
        await message.answer("❌ Ошибка", reply_markup=get_main_menu())
        await state.clear()
        return
    await db.add_content_post(title=f"Серия: {topic}", body=result, channel="series", status="draft")
    await message.bot.send_message(chat_id=LEADS_GROUP_CHAT_ID, message_thread_id=THREAD_ID_DRAFTS, text=f"📅 <b>Серия на {days} дней</b>\n\n{result}", parse_mode="HTML")
    await message.answer(f"✅ <b>Серия готова!</b>\n📊 {days} постов\n📁 В черновиках", reply_markup=get_main_menu(), parse_mode="HTML")
    await state.clear()

@content_router.message(F.text == "📰 Новость")
async def news_start(message: Message, state: FSMContext):
    await message.answer("📰 <b>Экспертная новость</b>\n\nВведите тему:", reply_markup=get_back_btn(), parse_mode="HTML")
    await state.set_state(ContentStates.news_topic)

@content_router.message(ContentStates.news_topic)
async def generate_news(message: Message, state: FSMContext):
    topic = message.text
    await message.answer("🔍 <b>Пишу новость...</b>", parse_mode="HTML")
    prompt = f"Напиши экспертную новость на тему «{topic}». 200-250 слов. Хештеги: #новость #недвижимость"
    news_text = await router_ai.generate(prompt)
    if not news_text:
        await message.answer("❌ Ошибка", reply_markup=get_main_menu())
        await state.clear()
        return
    post_id = await show_preview(message, news_text)
    await state.set_state(ContentStates.preview_mode)
    await state.update_data(post_id=post_id, text=news_text)

@