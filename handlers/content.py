"""
Content Handler — TERION Content Bot (TG + VK Edition)
Интеграция: Квин/Gemini (тексты) + Яндекс АРТ (изображения) + VK (публикация)
"""
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, KeyboardButton, FSInputFile,
    InputMediaPhoto
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
from datetime import datetime, timedelta
from typing import Optional
from PIL import Image
import io

from database import db
from handlers.vk_publisher import VKPublisher
from config import (
    CONTENT_BOT_TOKEN,
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
    VK_TOKEN,
    VK_GROUP_ID,
    VK_QUIZ_LINK
)

logger = logging.getLogger(__name__)
content_router = Router()

# ГЛОБАЛЬНЫЕ ОБРАБОТЧИКИ МЕНЮ (всегда активны)
@content_router.message(F.text.in_([
    "📸 Фото → Описание → Пост",
    "🎨 ИИ-Визуал", 
    "📅 7 дней прогрева",
    "📰 Новость",
    "📋 Интерактивный План",
    "📝 Быстрый текст"
]))
async def global_menu_handler(message: Message, state: FSMContext):
    """Глобальный обработчик меню — работает из любого состояния"""
    await state.clear()  # Сбрасываем FSM
    
    text = message.text
    
    if text == "📸 Фото → Описание → Пост":
        await photo_start(message, state)
    elif text == "🎨 ИИ-Визуал":
        await art_start(message, state)
    elif text == "📅 7 дней прогрева":
        await series_start(message, state)
    elif text == "📰 Новость":
        await news_start(message, state)
    elif text == "📋 Интерактивный План":
        await reply_menu_plan(message, state)
    elif text == "📝 Быстрый текст":
        await quick_start(message, state)

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


# === AI CLIENTS ===

class YandexArtClient:
    """Яндекс АРТ для генерации изображений"""
    
    def __init__(self, api_key: str, folder_id: str):
        self.api_key = api_key
        self.folder_id = folder_id
        self.headers = {
            "Authorization": f"Api-Key {api_key}",
            "Content-Type": "application/json"
        }
    
    async def generate(self, prompt: str) -> Optional[str]:
        """Генерация изображения, возвращает base64"""
        payload = {
            "modelUri": f"art://{self.folder_id}/yandex-art/latest",
            "messages": [{"weight": 1, "text": prompt}],
            "generationOptions": {
                "seed": int(datetime.now().timestamp()),
                "aspectRatio": {"widthRatio": 16, "heightRatio": 9}
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGeneration",
                    headers=self.headers,
                    json=payload
                ) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    op_id = data.get("id")
                    if not op_id:
                        return None
                    
                    # Polling
                    for _ in range(30):
                        await asyncio.sleep(2)
                        async with session.get(
                            f"https://operation.api.cloud.yandex.net/operations/{op_id}",
                            headers=self.headers
                        ) as check:
                            if check.status == 200:
                                result = await check.json()
                                if result.get("done"):
                                    return result.get("response", {}).get("image")
        except Exception as e:
            logger.error(f"YandexART error: {e}")
        return None


class RouterAIClient:
    """RouterAI для текстов и изображений"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def generate(
        self,
        prompt: str,
        model: str = "quin",
        max_tokens: int = 2000
    ) -> Optional[str]:
        """Генерация текста"""
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://routerai.ru/api/v1/chat/completions",
                    headers=self.headers,
                    json=payload
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"RouterAI error: {e}")
        return None
    
    async def analyze_image(self, image_b64: str, prompt: str) -> Optional[str]:
        """Анализ изображения через Gemini"""
        payload = {
            "model": "gemini-2.5-flash-image",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                ]
            }],
            "max_tokens": 1000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://routerai.ru/api/v1/chat/completions",
                    headers=self.headers,
                    json=payload
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Vision error: {e}")
        return None
    
    async def generate_image_gemini(self, prompt: str) -> Optional[str]:
        """
        Генерация изображения через Gemini 2.5 Flash Image (Nano Banana)
        Возвращает base64 или None
        """
        payload = {
            "model": "gemini-2.5-flash-image",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Generate image: {prompt}"}
                    ]
                }
            ],
            "max_tokens": 2000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://routerai.ru/api/v1/chat/completions",
                    headers=self.headers,
                    json=payload
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        content = data["choices"][0]["message"]["content"]
                        # Проверяем markdown с base64
                        if "data:image" in content:
                            import re
                            match = re.search(r'data:image/[^;]+;base64,([^"\']+)', content)
                            if match:
                                return match.group(1)
                        return content
                    else:
                        error = await resp.text()
                        logger.error(f"Gemini Image error: {error}")
                        return None
        except Exception as e:
            logger.error(f"Gemini Image exception: {e}")
            return None


# Инициализация
yandex_art = YandexArtClient(YANDEX_API_KEY, FOLDER_ID)
router_ai = RouterAIClient(ROUTER_AI_KEY)
import asyncio  # для yandex art polling


# === KEYBOARDS ===

def get_main_menu() -> ReplyKeyboardMarkup:
    """Главное меню"""
    kb = [
        [KeyboardButton(text="📸 Фото → Описание → Пост")],
        [KeyboardButton(text="🎨 ИИ-Визуал"), KeyboardButton(text="📅 7 дней прогрева")],
        [KeyboardButton(text="📰 Новость"), KeyboardButton(text="📋 Интерактивный План")],
        [KeyboardButton(text="📝 Быстрый текст")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_preview_keyboard(post_id: int, has_image: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура превью перед публикацией"""
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


# === HELPERS ===

async def safe_edit_message(message, text, reply_markup=None, parse_mode="HTML"):
    """Безопасное редактирование — работает и с текстом, и с фото"""
    try:
        if message.photo:
            await message.edit_caption(caption=text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await message.edit_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        logger.warning(f"Edit failed: {e}")
        # Отправляем новое сообщение
        await message.answer(text=text, reply_markup=reply_markup, parse_mode=parse_mode)


async def download_photo(bot: Bot, file_id: str) -> Optional[bytes]:
    """Скачать фото в байты"""
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
    """Сжатие изображения для экономии токенов Vision API"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        # Конвертируем в RGB если нужно
        if img.mode in ('RGBA', 'P', 'LA'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            if img.mode in ('RGBA', 'LA'):
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            else:
                img = img.convert('RGB')
        # Уменьшаем если большое
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            logger.info(f"Image resized: {img.size}")
        # Сохраняем с указанным качеством
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        compressed = output.getvalue()
        # Логируем экономию
        original_kb = len(image_bytes) / 1024
        compressed_kb = len(compressed) / 1024
        savings = (1 - len(compressed) / len(image_bytes)) * 100
        logger.info(f"Image compressed: {original_kb:.1f}KB → {compressed_kb:.1f}KB ({savings:.0f}% saved)")
        return compressed
    except Exception as e:
        logger.error(f"Compression error: {e}")
        return image_bytes


async def show_preview(
    message: Message,
    text: str,
    image_file_id: Optional[str] = None,
    post_id: Optional[int] = None
):
    """Показать превью поста с кнопками действий"""
    if not post_id:
        # Сохраняем в БД
        post_id = await db.add_content_post(
            title="Preview",
            body=text,
            image_url=image_file_id,
            channel="preview",
            status="preview"
        )
    
    kb = get_preview_keyboard(post_id, bool(image_file_id))
    
    if image_file_id:
        await message.answer_photo(
            photo=image_file_id,
            caption=f"👁 <b>Предпросмотр</b>\n\n{text}\n\n<i>Выберите действие:</i>",
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"👁 <b>Предпросмотр</b>\n\n{text}\n\n<i>Выберите действие:</i>",
            reply_markup=kb,
            parse_mode="HTML"
        )
    
    return post_id


# === HANDLERS ===

@content_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Старт"""
    await state.clear()
    await message.answer(
        "🎯 <b>TERION Content Bot</b>\n\n"
        "Создание и публикация контента:\n"
        "• Telegram (TERION + ДОМ ГРАНД)\n"
        "• ВКонтакте (с кнопками)\n\n"
        "Выберите действие:",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.main_menu)


# === 📸 ФОТО WORKFLOW ===

@content_router.message(F.text == "📸 Фото → Описание → Пост")
async def photo_start(message: Message, state: FSMContext):
    """Начало workflow с фото — сначала тема, потом фото"""
    await state.clear()
    await message.answer(
        "📸 <b>Фото → Описание → Пост</b>\n\n"
        "Шаг 1/2: Введите <b>тему поста</b> или опишите, что на фото:\n\n"
        "Примеры:\n"
        "• Перепланировка студии в старом фонде\n"
        "• Объединение кухни и гостиной\n"
        "• Ремонт ванной с перепланировкой\n\n"
        "Это поможет AI создать точное описание.",
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.photo_topic)


@content_router.message(ContentStates.photo_topic)
async def process_photo_topic(message: Message, state: FSMContext):
    """Получили тему, теперь просим фото"""
    topic = message.text
    await state.update_data(photo_topic=topic)
    
    await message.answer(
        f"✅ Тема: <b>{topic}</b>\n\n"
        f"Шаг 2/2: Загрузите <b>фото объекта</b> (1-3 фото):\n\n"
        f"• Поэтажный план\n"
        f"• Фото интерьера\n"
        f"• Схема перепланировки",
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.photo_upload)


@content_router.message(ContentStates.photo_upload, F.photo)
async def process_photo(message: Message, state: FSMContext):
    """Обработка фото с учетом темы — экспертное описание"""
    data = await state.get_data()
    topic = data.get('photo_topic', 'Перепланировка')
    
    photo = message.photo[-1]
    file_id = photo.file_id
    
    await message.answer(
        f"🔍 <b>Анализирую фото...</b>\n"
        f"Тема: {topic}\n"
        f"Создаю экспертное описание...",
        parse_mode="HTML"
    )
    
    # Скачиваем и сжимаем
    image_bytes = await download_photo(message.bot, file_id)
    if not image_bytes:
        await message.answer("❌ Ошибка загрузки", reply_markup=get_main_menu())
        await state.clear()
        return
    
    compressed = await compress_image(image_bytes, max_size=1024)
    image_b64 = base64.b64encode(compressed).decode()
    
    # ЭКСПЕРТНЫЙ ПРОМПТ (как в старом боте)
    prompt = (
        f"Ты — эксперт по перепланировкам с 10-летним опытом. "
        f"Тема поста: «{topic}»\n\n"
        f"Проанализируй фото и напиши экспертный пост:\n\n"
        f"Структура:\n"
        f"1. <b>Заголовок</b> — конкретный, без обещаний 'за 3 дня'\n"
        f"2. <b>Описание</b> — что видно на фото, особенности объекта\n"
        f"3. <b>Экспертный комментарий</b> — нюансы перепланировки\n"
        f"4. <b>Важно знать</b> — юридические/технические моменты\n"
        f"5. <b>Призыв</b> — консультация @terion_bot\n\n"
        f"Требования:\n"
        f"- Без фантастических обещаний ('за 3 дня', 'без проблем')\n"
        f"- Реальные сроки и сложности\n"
        f"- Конкретика по теме: {topic}\n"
        f"- Длина: 400-700 знаков\n"
        f"- Хештеги: #перепланировка #терион"
    )
    
    description = await router_ai.analyze_image(image_b64, prompt)
    
    if not description or len(description) < 100:
        # Fallback — шаблон как в старом боте
        description = (
            f"<b>При перепланировке квартиры важно понимать</b> нюансы работы "
            f"с конкретными элементами. Это требует профессионального подхода.\n\n"
            f"<b>Основные аспекты темы «{topic}»:</b>\n"
            f"• Проектирование и согласование\n"
            f"• Техническая реализация\n"
            f"• Юридическое оформление\n\n"
            f"Важно! Все работы должны выполняться с разрешения и под контролем специалистов.\n\n"
            f"📍 <a href='{VK_QUIZ_LINK}'>КВИЗ</a>\n"
            f"#перепланировка #терион"
        )
    
    # Сохраняем
    post_id = await db.add_content_post(
        title=f"Фото: {topic[:40]}",
        body=description,
        image_url=file_id,
        channel="photo_workflow",
        status="preview"
    )
    
    await state.update_data(post_id=post_id, description=description, file_id=file_id, image_bytes=image_bytes)
    
    # Показываем превью
    await message.answer_photo(
        photo=file_id,
        caption=f"👁 <b>Предпросмотр</b>\n\n{description[:700]}...",
        reply_markup=get_preview_keyboard(post_id, True),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.preview_mode)


# === 🎨 ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ ===

@content_router.message(F.text == "🎨 ИИ-Визуал")
async def art_start(message: Message, state: FSMContext):
    """Выбор модели для генерации изображения"""
    await state.clear()
    await message.answer(
        "🎨 <b>Генерация изображения</b>\n\n"
        "Выберите модель:\n\n"
        "<b>🟣 Яндекс АРТ</b>\n"
        "• Лучше для интерьеров\n"
        "• Русский промпт\n"
        "• 10-30 секунд\n\n"
        "<b>🟡 Gemini 2.5 Flash Image</b>\n"
        "• Быстрее (5-10 сек)\n"
        "• Nano Banana оптимизация\n"
        "• Через RouterAI\n\n"
        "Выберите:",
        reply_markup=InlineKeyboardBuilder()
        .button(text="🟣 Яндекс АРТ", callback_data="visual_model:yandex")
        .button(text="🟡 Gemini Nano", callback_data="visual_model:gemini")
        .button(text="◀️ Меню", callback_data="back_menu")
        .as_markup(),
        parse_mode="HTML"
    )


@content_router.callback_query(F.data.startswith("visual_model:"))
async def visual_model_selected(callback: CallbackQuery, state: FSMContext):
    """Выбрана модель для генерации"""
    model = callback.data.split(":")[1]
    await state.update_data(visual_model=model)
    
    model_name = "Яндекс АРТ" if model == "yandex" else "Gemini 2.5 Flash Image"
    
    await callback.answer(f"Выбрано: {model_name}")
    await callback.message.edit_text(
        f"🎨 <b>{model_name}</b>\n\n"
        f"Введите описание для генерации:\n\n"
        f"Примеры:\n"
        f"• Скандинавская гостиная с панорамными окнами\n"
        f"• Современная кухня-студия, остров, минимализм\n"
        f"• Перепланировка в старом фонде, до/после\n\n"
        f"Опишите детально: стиль, цвета, освещение, материалы.",
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.ai_visual_prompt)


@content_router.message(ContentStates.ai_visual_prompt)
async def ai_visual_handler(message: Message, state: FSMContext):
    """Генерация изображения — выбранная модель"""
    data = await state.get_data()
    model = data.get('visual_model', 'yandex')
    user_prompt = message.text
    
    await message.answer(
        f"⏳ <b>Генерация...</b>\n"
        f"Модель: {'Яндекс АРТ' if model == 'yandex' else 'Gemini Nano'}\n"
        f"Ожидание: {'10-30 сек' if model == 'yandex' else '5-10 сек'}",
        parse_mode="HTML"
    )
    
    # Улучшаем промпт
    enhanced_prompt = (
        f"{user_prompt}, professional architectural photography, "
        f"interior design, high quality, detailed, no text, no watermarks"
    )
    
    # Генерация по выбранной модели
    image_b64 = None
    model_used = ""
    
    if model == 'yandex':
        image_b64 = await yandex_art.generate(enhanced_prompt)
        model_used = "Яндекс АРТ"
    else:  # gemini
        image_b64 = await router_ai.generate_image_gemini(enhanced_prompt)
        model_used = "Gemini 2.5 Flash Image"
    
    # Проверка результата
    if not image_b64:
        await message.answer(
            f"❌ Ошибка генерации ({model_used})\n"
            f"Попробуйте:\n"
            f"• Другую модель\n"
            f"• Более простое описание",
            reply_markup=InlineKeyboardBuilder()
            .button(text="🔄 Повторить", callback_data="visual_back")
            .button(text="◀️ Меню", callback_data="back_menu")
            .as_markup(),
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    # Отправляем результат
    try:
        image_bytes = base64.b64decode(image_b64)
        
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name
        
        await message.answer_photo(
            photo=FSInputFile(tmp_path),
            caption=(
                f"✅ <b>Готово!</b>\n\n"
                f"🎨 <b>Модель:</b> {model_used}\n"
                f"📝 <b>Промпт:</b> <code>{user_prompt[:60]}...</code>\n\n"
                f"Что сделать с изображением?"
            ),
            reply_markup=InlineKeyboardBuilder()
            .button(text="📝 Создать пост", callback_data=f"art_to_post:{user_prompt}:{model}")
            .button(text="🔄 Другая модель", callback_data="visual_back")
            .button(text="💾 Скачать", callback_data=f"download_art:{model}")
            .button(text="◀️ Меню", callback_data="back_menu")
            .adjust(2, 1, 1)
            .as_markup(),
            parse_mode="HTML"
        )
        
        os.unlink(tmp_path)
        
    except Exception as e:
        logger.error(f"Send image error: {e}")
        await message.answer("❌ Ошибка отправки изображения", reply_markup=get_main_menu())
    
    await state.clear()


@content_router.callback_query(F.data == "visual_back")
async def visual_back(callback: CallbackQuery, state: FSMContext):
    """Вернуться к выбору модели"""
    await callback.answer()
    await art_start(callback.message, state)


@content_router.callback_query(F.data.startswith("art_to_post:"))
async def art_to_post(callback: CallbackQuery, state: FSMContext):
    """Создать пост из арта"""
    parts = callback.data.split(":", 2)
    prompt = parts[1]
    model = parts[2] if len(parts) > 2 else 'yandex'
    
    await callback.answer("Введите текст поста")
    await callback.message.answer(
        f"📝 <b>Создание поста с изображением</b>\n\n"
        f"<b>Промпт:</b> <code>{prompt}</code>\n\n"
        f"Введите текст поста:",
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.quick_text)
    await state.update_data(art_prompt=prompt, has_image=True, art_model=model)


# === 📅 7 ДНЕЙ ПРОГРЕВА ===

@content_router.message(F.text == "📅 7 дней прогрева")
async def series_start(message: Message, state: FSMContext):
    """📅 7 дней прогрева — сразу запрашиваем тему"""
    await message.answer(
        "📅 <b>7 дней прогрева</b>\n\n"
        "Введите тему для серии постов:\n"
        "Например: «Мастер-спальни в современных квартирах»",
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )
    await state.update_data(days=7)
    await state.set_state(ContentStates.series_topic)


@content_router.message(ContentStates.series_days)
async def series_days_input(message: Message, state: FSMContext):
    """Ввод количества дней"""
    try:
        days = int(message.text)
        if days < 1 or days > 60:
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите число от 1 до 60")
        return
    
    await state.update_data(days=days)
    await message.answer(
        f"✅ <b>{days} дней</b>\n\n"
        f"Введите тему серии:\n"
        f"Например: «Мастер-спальни в современных квартирах»",
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.series_topic)


@content_router.message(ContentStates.series_topic)
async def generate_series(message: Message, state: FSMContext):
    """Генерация серии"""
    data = await state.get_data()
    days = data.get("days", 7)
    topic = message.text
    
    await message.answer(f"⏳ <b>Генерирую {days} постов...</b>", parse_mode="HTML")
    
    prompt = (
        f"Создай {days} постов для прогрева по теме «{topic}». "
        f"Формат: JSON массив с полями day, title, text. "
        f"Каждый пост: заголовок до 60 символов, текст 80-120 слов, "
        f"призыв к консультации. Тон: экспертный."
    )
    
    result = await router_ai.generate(prompt, max_tokens=4000)
    if not result:
        await message.answer("❌ Ошибка", reply_markup=get_main_menu())
        await state.clear()
        return
    
    # Парсим и сохраняем
    try:
        # Очистка markdown
        json_str = result
        if "```json" in result:
            json_str = result.split("```json")[1].split("```")[0]
        elif "```" in result:
            json_str = result.split("```")[1].split("```")[0]
        
        posts = json.loads(json_str.strip())
        post_ids = []
        
        for i, post in enumerate(posts[:days], 1):
            text = f"<b>{post.get('title', f'День {i}')}</b>\n\n{post.get('text', '')}\n\n#перепланировка"
            post_id = await db.add_content_post(
                title=f"День {i}: {post.get('title', '')}",
                body=text,
                channel="series",
                status="draft",
                scheduled_date=datetime.now() + timedelta(days=i)
            )
            post_ids.append(post_id)
        
        # Отправляем в рабочую группу
        preview = f"📅 <b>Серия на {days} дней</b>\n\n<b>Тема:</b> {topic}\n<b>Постов:</b> {len(post_ids)}\n\n"
        for i, post in enumerate(posts[:3], 1):
            preview += f"<b>День {i}:</b> {post.get('title', '')}\n"
        
        await message.bot.send_message(
            chat_id=LEADS_GROUP_CHAT_ID,
            message_thread_id=THREAD_ID_DRAFTS,
            text=preview,
            parse_mode="HTML"
        )
        
        await message.answer(
            f"✅ <b>Серия готова!</b>\n"
            f"📊 Постов: {len(post_ids)}\n"
            f"📁 В черновиках (топик 85)",
            reply_markup=get_main_menu(),
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Series error: {e}")
        # Сохраняем как один пост
        await db.add_content_post(title=f"Серия: {topic}", body=result, channel="series", status="draft")
        await message.answer("⚠️ Сохранил как документ", reply_markup=get_main_menu())
    
    await state.clear()


# === 📰 НОВОСТЬ ===

@content_router.message(F.text == "📰 Новость")
async def news_start(message: Message, state: FSMContext):
    """Новостной пост"""
    await message.answer(
        "📰 <b>Экспертная новость</b>\n\n"
        "Введите тему:\n"
        "• Перепланировка — изменения в законе\n"
        "• Ипотека — ставки, программы\n"
        "• Строительство — новые технологии",
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.news_topic)


@content_router.message(ContentStates.news_topic)
async def generate_news(message: Message, state: FSMContext):
    """Генерация новости"""
    topic = message.text
    
    await message.answer("🔍 <b>Пишу новость...</b>", parse_mode="HTML")
    
    prompt = (
        f"Напиши экспертную новость на тему «{topic}». "
        f"Структура: 1) Заголовок 2) Суть новости 3) Комментарий эксперта "
        f"4) Что делать 5) Призыв к консультации. "
        f"200-250 слов. Хештеги: #новость #недвижимость #TERION"
    )
    
    news_text = await router_ai.generate(prompt)
    if not news_text:
        await message.answer("❌ Ошибка", reply_markup=get_main_menu())
        await state.clear()
        return
    
    post_id = await show_preview(message, news_text)
    await state.set_state(ContentStates.preview_mode)
    await state.update_data(post_id=post_id, text=news_text)


# === 📋 ИНТЕРАКТИВНЫЙ ПЛАН ===

@content_router.message(F.text == "📋 Интерактивный План")
async def reply_menu_plan(message: Message, state: FSMContext):
    """Интерактивный план — сразу дни + тема"""
    await state.clear()
    await message.answer(
        "📋 <b>Интерактивный план</b>\n\n"
        "Введите через запятую:\n"
        "<code>количество дней, тема плана</code>\n\n"
        "Примеры:\n"
        "• <code>3, переустройство ванной комнаты</code>\n"
        "• <code>5, объединение кухни и гостиной</code>\n"
        "• <code>7, перепланировка в сталинском доме</code>\n\n"
        "Бот создаст план с постами и предложит сгенерировать изображения.",
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.ai_plan)


@content_router.message(ContentStates.ai_plan)
async def ai_plan_handler(message: Message, state: FSMContext):
    """Обработка: дни + тема → генерация плана"""
    text = message.text.strip()
    
    # Парсим ввод
    try:
        if ',' in text:
            parts = [p.strip() for p in text.split(',', 1)]
            days = int(parts[0])
            topic = parts[1]
        else:
            await message.answer(
                "❌ Неверный формат. Введите:\n"
                "<code>число, тема</code>\n\n"
                "Пример: <code>3, переустройство ванной</code>",
                parse_mode="HTML"
            )
            return
    except (ValueError, IndexError):
        await message.answer("❌ Введите число и тему через запятую")
        return
    
    if days < 1 or days > 30:
        await message.answer("❌ Введите число от 1 до 30")
        return
    
    await message.answer(
        f"⏳ <b>Создаю план на {days} дней...</b>\n"
        f"Тема: {topic}\n"
        f"Генерация через Квин...",
        parse_mode="HTML"
    )
    
    # Генерируем план
    prompt = (
        f"Создай контент-план на {days} дней для эксперта по перепланировкам.\n"
        f"Тема: «{topic}»\n\n"
        f"Для каждого дня укажи:\n"
        f"• День N: Заголовок поста\n"
        f"• Краткое содержание (2-3 предложения)\n"
        f"• Формат (текст/фото/карусель)\n"
        f"• Идея для изображения (если нужно фото)\n\n"
        f"Тон: экспертный, практичный. Добавь эмодзи."
    )
    
    plan = await router_ai.generate(prompt, model="quin", max_tokens=3000)
    
    if not plan:
        await message.answer("❌ Ошибка генерации", reply_markup=get_main_menu())
        await state.clear()
        return
    
    # Сохраняем
    post_id = await db.add_content_post(
        title=f"План {days} дней: {topic[:40]}",
        body=plan,
        channel="content_plan",
        status="draft"
    )
    
    # Отправляем в топик контент-плана
    await message.bot.send_message(
        chat_id=LEADS_GROUP_CHAT_ID,
        message_thread_id=THREAD_ID_CONTENT_PLAN,
        text=f"📋 <b>План на {days} дней</b>\n\n<b>Тема:</b> {topic}\n\n{plan[:1500]}...",
        parse_mode="HTML"
    )
    
    # Спрашиваем про изображения с выбором модели
    await message.answer(
        f"✅ <b>План готов!</b>\n"
        f"📊 {days} дней\n"
        f"📁 Отправлен в топик 83\n\n"
        f"<b>Сгенерировать изображения?</b>\n"
        f"Выберите модель:",
        reply_markup=InlineKeyboardBuilder()
        .button(text="🟣 Яндекс АРТ (качество)", callback_data=f"gen_images_yandex:{post_id}:{days}:{topic}")
        .button(text="🟡 Gemini Nano (скорость)", callback_data=f"gen_images_gemini:{post_id}:{days}:{topic}")
        .button(text="❌ Нет", callback_data="back_menu")
        .as_markup(),
        parse_mode="HTML"
    )
    await state.clear()


# === 📝 БЫСТРЫЙ ТЕКСТ ===

@content_router.message(F.text == "📝 Быстрый текст")
async def quick_start(message: Message, state: FSMContext):
    """Быстрый текст"""
    await message.answer(
        "📝 <b>Быстрый текст</b>\n\n"
        "Введите тему:",
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.quick_text)


@content_router.message(ContentStates.quick_text)
async def generate_quick(message: Message, state: FSMContext):
    """Генерация быстрого текста"""
    topic = message.text
    
    await message.answer("⏳ <b>Пишу...</b>", parse_mode="HTML")
    
    prompt = (
        f"Напиши пост для TG на тему «{topic}». "
        f"Стиль: экспертный, живой. 100-150 слов. "
        f"Эмодзи + призыв @terion_bot"
    )
    
    text = await router_ai.generate(prompt)
    if not text:
        await message.answer("❌ Ошибка", reply_markup=get_main_menu())
        await state.clear()
        return
    
    # Проверяем, есть ли изображение из арта
    data = await state.get_data()
    art_prompt = data.get("art_prompt")
    
    if art_prompt:
        # Нужно перегенерировать или использовать сохраненное
        await message.answer("🎨 <b>Генерирую изображение заново...</b>", parse_mode="HTML")
        enhanced = f"{art_prompt}, professional interior photography, high quality, detailed, no text"
        image_b64 = await yandex_art.generate(enhanced)
        
        if image_b64:
            image_bytes = base64.b64decode(image_b64)
            # Сохраняем временно для превью
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name
            
            # Отправляем превью с фото
            msg = await message.answer_photo(
                photo=FSInputFile(tmp_path),
                caption=f"👁 <b>Предпросмотр</b>\n\n{text}",
                parse_mode="HTML"
            )
            os.unlink(tmp_path)
            
            post_id = await db.add_content_post(
                title=f"Арт: {art_prompt[:30]}",
                body=text,
                image_url=msg.photo[-1].file_id,
                channel="art_post",
                status="preview"
            )
            
            await msg.edit_reply_markup(reply_markup=get_preview_keyboard(post_id, True))
            await state.update_data(post_id=post_id, text=text, file_id=msg.photo[-1].file_id, image_bytes=image_bytes)
            await state.set_state(ContentStates.preview_mode)
            return
    
    # Без изображения
    post_id = await show_preview(message, text)
    await state.set_state(ContentStates.preview_mode)
    await state.update_data(post_id=post_id, text=text)


# === ПУБЛИКАЦИЯ (ПРЕВЬЮ КНОПКИ) ===

@content_router.callback_query(F.data.startswith("pub_all:"))
async def publish_all(callback: CallbackQuery, state: FSMContext):
    """Публикация везде: TG + VK"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    if not post:
        await callback.answer("❌ Пост не найден")
        return
    
    await callback.answer("🚀 Публикую...")
    await safe_edit_message(callback.message, "🚀 <b>Публикация...</b>")
    
    results = []
    image_bytes = None
    
    # Если есть фото — скачиваем для VK
    if post.get("image_url"):
        image_bytes = await download_photo(callback.bot, post["image_url"])
    
    # 1. TERION TG
    try:
        if post.get("image_url"):
            await callback.bot.send_photo(
                chat_id=CHANNEL_ID_TERION,
                photo=post["image_url"],
                caption=post["body"],
                parse_mode="HTML"
            )
        else:
            await callback.bot.send_message(
                chat_id=CHANNEL_ID_TERION,
                text=post["body"],
                parse_mode="HTML"
            )
        results.append("✅ TERION TG")
    except Exception as e:
        logger.error(f"TERION error: {e}")
        results.append("❌ TERION TG")
    
    # 2. ДОМ ГРАНД TG
    try:
        if post.get("image_url"):
            await callback.bot.send_photo(
                chat_id=CHANNEL_ID_DOM_GRAD,
                photo=post["image_url"],
                caption=post["body"],
                parse_mode="HTML"
            )
        else:
            await callback.bot.send_message(
                chat_id=CHANNEL_ID_DOM_GRAD,
                text=post["body"],
                parse_mode="HTML"
            )
        results.append("✅ ДОМ ГРАНД TG")
    except Exception as e:
        logger.error(f"DOM GRAND error: {e}")
        results.append("❌ ДОМ ГРАНД TG")
    
    # 3. VK
    try:
        if image_bytes:
            vk_post_id = await vk_publisher.post_with_photo(
                post["body"],
                image_bytes,
                add_buttons=True
            )
        else:
            vk_post_id = await vk_publisher.post_text_only(
                post["body"],
                add_buttons=True
            )
        
        if vk_post_id:
            results.append(f"✅ VK (post{vk_post_id})")
        else:
            results.append("❌ VK")
    except Exception as e:
        logger.error(f"VK error: {e}")
        results.append("❌ VK")
    
    # Обновляем статус
    await db.update_content_post(post_id, status="published")
    
    # Отправляем лог в рабочую группу
    log_text = (
        f"🚀 <b>Публикация #{post_id}</b>\n\n"
        + "\n".join(results) + "\n\n"
        f"<b>Текст:</b> {post['body'][:200]}..."
    )
    await callback.bot.send_message(
        chat_id=LEADS_GROUP_CHAT_ID,
        message_thread_id=THREAD_ID_LOGS,
        text=log_text,
        parse_mode="HTML"
    )
    
    await safe_edit_message(
        callback.message,
        f"✅ <b>Опубликовано!</b>\n\n" + "\n".join(results),
        reply_markup=get_main_menu()
    )
    await state.clear()


@content_router.callback_query(F.data.startswith("pub_tg:"))
async def publish_tg_only(callback: CallbackQuery, state: FSMContext):
    """Только Telegram (оба канала)"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    results = []
    
    # TERION
    try:
        if post.get("image_url"):
            await callback.bot.send_photo(CHANNEL_ID_TERION, post["image_url"], post["body"], parse_mode="HTML")
        else:
            await callback.bot.send_message(CHANNEL_ID_TERION, post["body"], parse_mode="HTML")
        results.append("✅ TERION")
    except Exception as e:
        results.append("❌ TERION")
    
    # ДОМ ГРАНД
    try:
        if post.get("image_url"):
            await callback.bot.send_photo(CHANNEL_ID_DOM_GRAD, post["image_url"], post["body"], parse_mode="HTML")
        else:
            await callback.bot.send_message(CHANNEL_ID_DOM_GRAD, post["body"], parse_mode="HTML")
        results.append("✅ ДОМ ГРАНД")
    except Exception as e:
        results.append("❌ ДОМ ГРАНД")
    
    await db.update_content_post(post_id, status="published")
    await safe_edit_message(
        callback.message,
        f"✅ <b>Telegram:</b>\n" + "\n".join(results),
        reply_markup=get_main_menu()
    )
    await state.clear()


@content_router.callback_query(F.data.startswith("pub_vk:"))
async def publish_vk_only(callback: CallbackQuery, state: FSMContext):
    """Только ВКонтакте"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    # Скачиваем фото если есть
    image_bytes = None
    if post.get("image_url"):
        image_bytes = await download_photo(callback.bot, post["image_url"])
    
    try:
        if image_bytes:
            vk_id = await vk_publisher.post_with_photo(post["body"], image_bytes, add_buttons=True)
        else:
            vk_id = await vk_publisher.post_text_only(post["body"], add_buttons=True)
        
        if vk_id:
            await db.update_content_post(post_id, status="published")
            await safe_edit_message(
                callback.message,
                f"✅ <b>VK:</b> post{vk_id}",
                reply_markup=get_main_menu()
            )
        else:
            await callback.answer("❌ Ошибка VK")
    except Exception as e:
        logger.error(f"VK only error: {e}")
        await callback.answer("❌ Ошибка")
    
    await state.clear()


@content_router.callback_query(F.data.startswith("draft:"))
async def save_draft(callback: CallbackQuery, state: FSMContext):
    """Сохранить в черновики"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    try:
        # Отправляем в топик черновиков
        if post.get("image_url"):
            await callback.bot.send_photo(
                chat_id=LEADS_GROUP_CHAT_ID,
                message_thread_id=THREAD_ID_DRAFTS,
                photo=post["image_url"],
                caption=f"📝 <b>Черновик #{post_id}</b>\n\n{post['body']}",
                parse_mode="HTML"
            )
        else:
            await callback.bot.send_message(
                chat_id=LEADS_GROUP_CHAT_ID,
                message_thread_id=THREAD_ID_DRAFTS,
                text=f"📝 <b>Черновик #{post_id}</b>\n\n{post['body']}",
                parse_mode="HTML"
            )
        
        await db.update_content_post(post_id, status="in_drafts")
        await callback.answer("✅ В черновиках")
        await safe_edit_message(callback.message, "✅ Отправлено в черновики (топик 85)", reply_markup=get_main_menu())
    except Exception as e:
        logger.error(f"Draft error: {e}")
        await callback.answer("❌ Ошибка")
    
    await state.clear()


@content_router.callback_query(F.data.startswith("edit:"))
async def edit_handler(callback: CallbackQuery, state: FSMContext):
    """Редактирование поста"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)

    if not post:
        await callback.answer("❌ Пост не найден")
        return

    await state.update_data({"edit_post_id": post_id})
    
    # Отправляем новое сообщение (безопасно для фото)
    await callback.message.answer(
        f"✏️ <b>Редактирование поста #{post_id}</b>\n\n"
        f"<b>Текущий текст:</b>\n{post['body'][:500]}...\n\n"
        f"Введите новый текст:",
        parse_mode="HTML"
    )
    await callback.answer()
    await state.set_state(ContentStates.preview_mode)


@content_router.callback_query(F.data == "cancel")
async def cancel_post(callback: CallbackQuery, state: FSMContext):
    """Отмена"""
    await callback.answer("❌ Отменено")
    await safe_edit_message(callback.message, "❌ Отменено", reply_markup=get_main_menu())
    await state.clear()


@content_router.callback_query(F.data == "back_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Назад в меню"""
    await callback.answer()
    await state.clear()
    await callback.message.answer(
        "🎯 <b>TERION Content Bot</b>",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )


@content_router.callback_query(F.data == "regen_art")
async def regen_art(callback: CallbackQuery, state: FSMContext):
    """Повторная генерация арта"""
    await callback.answer("🔄 Новая генерация")
    await art_start(callback.message, state)


# === ОБРАБОТКА ОШИБОК ===

@content_router.message(ContentStates.photo_upload)
async def wrong_photo(message: Message, state: FSMContext):
    """Если прислали не фото"""
    await message.answer("❌ Пожалуйста, отправьте фото или нажмите «Назад»")