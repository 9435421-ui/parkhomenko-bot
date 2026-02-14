"""
Content Handler — TERION Ecosystem (RouterAI + YandexART Edition)
TG + VK публикация, AI-генерация контента, квиз-интеграция
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
import io
import asyncio
import re
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
    MAX_API_KEY,
    YANDEX_ART_ENABLED,
    VK_TOKEN,
    VK_GROUP_ID,
    VK_QUIZ_LINK,
    CHANNEL_NAMES
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
        await visual_select_model(message, state)
    elif text == "📅 7 дней прогрева":
        await series_start(message, state)
    elif text == "📰 Новость":
        await news_start(message, state)
    elif text == "📋 Интерактивный План":
        await plan_start(message, state)
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
                        logger.error(f"YandexART HTTP {resp.status}")
                        return None
                    data = await resp.json()
                    op_id = data.get("id")
                    if not op_id:
                        return None
                    
                    # Polling
                    for i in range(30):
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
    
    async def generate(self, prompt: str, model: str = "openai/gpt-4o", max_tokens: int = 2000) -> Optional[str]:
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
                    else:
                        logger.error(f"RouterAI HTTP {resp.status}: {await resp.text()}")
        except Exception as e:
            logger.error(f"RouterAI error: {e}")
        return None
    
    async def analyze_image(self, image_b64: str, prompt: str) -> Optional[str]:
        """Анализ изображения через Gemini 1.5 Flash"""
        payload = {
            "model": "gemini-1.5-flash",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                ]
            }],
            "max_tokens": 1500
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
        """Генерация изображения через Gemini"""
        payload = {
            "model": "gemini-1.5-flash",
            "messages": [{
                "role": "user",
                "content": f"Generate image: {prompt}. Professional architectural photography, interior design, high quality, no text."
            }],
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
                        # Парсим base64
                        if "data:image" in content:
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


# === VK PUBLISHER ===

class VKPublisher:
    """Публикация в ВКонтакте с кнопками квиз/консультация"""
    
    def __init__(self, token: str, group_id: int):
        self.token = token
        self.group_id = group_id
        self.api_version = "5.199"
    
    async def _make_request(self, method: str, params: dict) -> Optional[dict]:
        params.update({"access_token": self.token, "v": self.api_version})
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.vk.com/method/{method}", params=params) as resp:
                    data = await resp.json()
                    if "error" in data:
                        logger.error(f"VK API error: {data['error']}")
                        return None
                    return data.get("response")
        except Exception as e:
            logger.error(f"VK request error: {e}")
            return None
    
    async def upload_photo(self, image_data: bytes) -> Optional[str]:
        """Загрузка фото на сервер ВК"""
        upload_data = await self._make_request("photos.getWallUploadServer", {"group_id": self.group_id})
        if not upload_data or not upload_data.get("upload_url"):
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field("photo", image_data, filename="photo.jpg", content_type="image/jpeg")
                
                async with session.post(upload_data["upload_url"], data=form) as resp:
                    result = await resp.json()
                    if "error" in result:
                        return None
                    
                    save_data = await self._make_request(
                        "photos.saveWallPhoto",
                        {
                            "group_id": self.group_id,
                            "photo": result.get("photo"),
                            "server": result.get("server"),
                            "hash": result.get("hash")
                        }
                    )
                    
                    if save_data and len(save_data) > 0:
                        photo = save_data[0]
                        return f"photo{photo['owner_id']}_{photo['id']}"
        except Exception as e:
            logger.error(f"VK upload error: {e}")
        return None
    
    def create_buttons(self, quiz_link: str = None, consult_link: str = None) -> str:
        """Кнопки: Квиз и Консультация"""
        if not quiz_link:
            quiz_link = VK_QUIZ_LINK
        if not consult_link:
            consult_link = "https://t.me/terion_bot?start=consult"
        
        buttons = {
            "inline": True,
            "buttons": [
                [{"action": {"type": "open_link", "link": quiz_link, "label": "📝 Пройти квиз"}}],
                [{"action": {"type": "open_link", "link": consult_link, "label": "💬 Бесплатная консультация"}}]
            ]
        }
        return json.dumps(buttons, ensure_ascii=False)
    
    async def post_to_wall(self, message: str, photo_id: Optional[str] = None) -> Optional[int]:
        """Публикация поста"""
        attachments = [photo_id] if photo_id else []
        
        params = {
            "owner_id": -self.group_id,
            "from_group": 1,
            "message": message,
            "attachments": ",".join(attachments),
            "keyboard": self.create_buttons()
        }
        
        result = await self._make_request("wall.post", params)
        return result.get("post_id") if result else None
    
    async def post_text_only(self, message: str) -> Optional[int]:
        return await self.post_to_wall(message, None)
    
    async def post_with_photo(self, message: str, image_bytes: bytes) -> Optional[int]:
        photo_id = await self.upload_photo(image_bytes)
        if not photo_id:
            return await self.post_text_only(message)
        return await self.post_to_wall(message, photo_id)


# Инициализация VK
vk_publisher = VKPublisher(VK_TOKEN, VK_GROUP_ID)


# === FSM STATES ===

class ContentStates(StatesGroup):
    main_menu = State()
    photo_topic = State()
    photo_upload = State()
    preview_mode = State()
    ai_text = State()
    ai_series = State()
    ai_visual_select = State()
    ai_visual_prompt = State()
    ai_plan = State()
    ai_news = State()
    edit_post = State()


# === KEYBOARDS ===

def get_main_menu() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="📸 Фото → Описание → Пост")],
        [KeyboardButton(text="🎨 ИИ-Визуал"), KeyboardButton(text="📅 7 дней прогрева")],
        [KeyboardButton(text="📰 Новость"), KeyboardButton(text="📋 Интерактивный План")],
        [KeyboardButton(text="📝 Быстрый текст")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_preview_keyboard(post_id: int, has_image: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Опубликовать: TERION", callback_data=f"pub_terion:{post_id}")
    builder.button(text="🏘 Опубликовать: ДОМ ГРАНД", callback_data=f"pub_dom_grnd:{post_id}")
    builder.button(text="🌐 Только VK", callback_data=f"pub_vk:{post_id}")
    builder.button(text="🗑 В черновики", callback_data=f"draft:{post_id}")
    builder.button(text="✏️ Редактировать", callback_data=f"edit:{post_id}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1, 1, 1, 1, 1)
    return builder.as_markup()


def get_queue_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """Кнопки для меню Очередь постов"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Опубликовать: TERION", callback_data=f"pub_terion:{post_id}")
    builder.button(text="🏘 Опубликовать: ДОМ ГРАНД", callback_data=f"pub_dom_grnd:{post_id}")
    builder.button(text="🗑 В черновики", callback_data=f"draft:{post_id}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1, 1, 1, 1)
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
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            logger.info(f"Image resized: {img.size}")
        # Сохраняем с указанным качеством
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        compressed = output.getvalue()
        
        original_kb = len(image_bytes) / 1024
        compressed_kb = len(compressed) / 1024
        logger.info(f"Image: {original_kb:.1f}KB → {compressed_kb:.1f}KB ({(1-len(compressed)/len(image_bytes))*100:.0f}%)")
        
        return compressed
    except Exception as e:
        logger.error(f"Compression error: {e}")
        return image_bytes


async def show_preview(message: Message, text: str, image_file_id: Optional[str] = None, post_id: Optional[int] = None):
    if not post_id:
        # Сохраняем в БД
        post_id = await db.add_content_post(
            title="Preview",
            body=text,
            cta="",
            image_url=image_file_id,
            channel="preview",
            status="preview"
        )
    
    kb = get_preview_keyboard(post_id, bool(image_file_id))
    caption = f"👁 <b>Предпросмотр</b>\n\n{text[:700]}{'...' if len(text) > 700 else ''}"
    
    if image_file_id:
        await message.answer_photo(photo=image_file_id, caption=caption, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(caption, reply_markup=kb, parse_mode="HTML")
    return post_id


# === GLOBAL MENU ===

@content_router.message(F.text.in_([
    "📸 Фото → Описание → Пост",
    "🎨 ИИ-Визуал",
    "📅 Серия постов",
    "📰 Новость",
    "📋 Контент-план",
    "📝 Быстрый текст"
]))
async def global_menu_handler(message: Message, state: FSMContext):
    await state.clear()
    text = message.text
    
    if text == "📸 Фото → Описание → Пост":
        await photo_start(message, state)
    elif text == "🎨 ИИ-Визуал":
        await visual_select_model(message, state)
    elif text == "📅 Серия постов":
        await series_start(message, state)
    elif text == "📰 Новость":
        await news_start(message, state)
    elif text == "📋 Контент-план":
        await plan_start(message, state)
    elif text == "📝 Быстрый текст":
        await quick_start(message, state)


# === 📸 ФОТО WORKFLOW ===

async def photo_start(message: Message, state: FSMContext):
    await message.answer(
        "📸 <b>Фото → Описание → Пост</b>\n\n"
        "Шаг 1/2: Введите <b>тему поста</b>:\n\n"
        "Примеры:\n"
        "• Перепланировка студии в старом фонде\n"
        "• Объединение кухни и гостиной\n"
        "• Ремонт ванной с перепланировкой",
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.photo_topic)


@content_router.message(ContentStates.photo_topic)
async def process_photo_topic(message: Message, state: FSMContext):
    topic = message.text
    await state.update_data(photo_topic=topic)
    
    await message.answer(
        f"✅ Тема: <b>{topic}</b>\n\n"
        f"Шаг 2/2: Загрузите <b>фото</b> (поэтажный план, интерьер):",
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.photo_upload)


@content_router.message(ContentStates.photo_upload, F.photo)
async def process_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    topic = data.get('photo_topic', 'Перепланировка')
    
    photo = message.photo[-1]
    file_id = photo.file_id
    
    await message.answer(f"🔍 <b>Анализирую фото...</b>\nТема: {topic}", parse_mode="HTML")
    
    image_bytes = await download_photo(message.bot, file_id)
    if not image_bytes:
        await message.answer("❌ Ошибка загрузки", reply_markup=get_back_btn())
        await state.clear()
        return
    
    compressed = await compress_image(image_bytes, max_size=1024)
    image_b64 = base64.b64encode(compressed).decode()
    
    prompt = (
        f"Ты — эксперт по перепланировкам. Тема: «{topic}»\n\n"
        f"Проанализируй фото и напиши пост:\n"
        f"1. <b>Заголовок</b> — конкретный, профессиональный, без клише 'уникальный дизайн' и 'за 3 дня'\n"
        f"2. <b>Описание</b> — что на фото, особенности объекта, тип здания\n"
        f"3. <b>Экспертный комментарий</b> — нюансы перепланировки, требования Жилищной инспекции, МНИИТЭП\n"
        f"4. <b>Важно</b> — юридические/технические моменты, согласование, проектная документация\n"
        f"5. <b>Призыв</b> — консультация @terion_bot\n\n"
        f"Требования: стиль профессиональный, экспертный, московское бюро перепланировок. Избегай клише 'уникальный дизайн' и 'за 3 дня'. Используй юридические термины (Жилищная инспекция, проект, МНИИТЭП). Реальные сроки, 400-700 знаков, эмодзи."
    )
    
    description = await router_ai.analyze_image(image_b64, prompt)
    
    if not description or len(description) < 100:
        description = (
            f"<b>При перепланировке важно учитывать</b> особенности объекта.\n\n"
            f"<b>Тема:</b> {topic}\n\n"
            f"• Проектирование и согласование\n"
            f"• Техническая реализация\n"
            f"• Юридическое оформление\n\n"
            f"Все работы — только с разрешения и под контролем специалистов.\n\n"
            f"📍 <a href='{VK_QUIZ_LINK}'>Пройти квиз</a>\n"
            f"#перепланировка #терион"
        )
    
    if VK_QUIZ_LINK not in description:
        description += f"\n\n📍 <a href='{VK_QUIZ_LINK}'>Пройти квиз</a> @terion_bot\n#TERION #перепланировка #москва"
    
    post_id = await db.add_content_post(
        title=f"Фото: {topic[:40]}",
        body=description,
        cta="",
        image_url=file_id,
        channel="photo_workflow",
        status="preview"
    )
    
    await state.update_data(post_id=post_id, description=description, file_id=file_id, image_bytes=image_bytes)
    
    await message.answer_photo(
        photo=file_id,
        caption=f"👁 <b>Предпросмотр</b>\n\n{description[:700]}{'...' if len(description) > 700 else ''}",
        reply_markup=get_preview_keyboard(post_id, True),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.preview_mode)


# === 🎨 ИИ-ВИЗУАЛ ===

async def visual_select_model(message: Message, state: FSMContext):
    await message.answer(
        "🎨 <b>Генерация изображения</b>\n\n"
        "Выберите модель:\n\n"
        "<b>🟣 Яндекс АРТ</b> — качество, 10-30 сек\n"
        "<b>🟡 Gemini Nano</b> — скорость, 5-10 сек",
        reply_markup=InlineKeyboardBuilder()
        .button(text="🟣 Яндекс АРТ", callback_data="visual_model:yandex")
        .button(text="🟡 Gemini Nano", callback_data="visual_model:gemini")
        .button(text="◀️ Назад", callback_data="back_menu")
        .as_markup(),
        parse_mode="HTML"
    )


@content_router.callback_query(F.data.startswith("visual_model:"))
async def visual_model_selected(callback: CallbackQuery, state: FSMContext):
    model = callback.data.split(":")[1]
    await state.update_data(visual_model=model)
    
    model_name = "Яндекс АРТ" if model == "yandex" else "Gemini Nano"
    
    await callback.answer(f"Выбрано: {model_name}")
    await callback.message.edit_text(
        f"🎨 <b>{model_name}</b>\n\n"
        f"Введите описание:\n\n"
        f"Примеры:\n"
        f"• Скандинавская гостиная с панорамными окнами\n"
        f"• Современная кухня-студия, минимализм\n"
        f"• Перепланировка в сталинке, до/после",
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.ai_visual_prompt)


@content_router.message(ContentStates.ai_visual_prompt)
async def ai_visual_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    model = data.get('visual_model', 'yandex')
    user_prompt = message.text
    
    await message.answer(
        f"⏳ <b>Генерация...</b>\n"
        f"Модель: {'Яндекс АРТ' if model == 'yandex' else 'Gemini Nano'}",
        parse_mode="HTML"
    )
    
    enhanced = f"{user_prompt}, professional architectural photography, interior design, high quality, detailed, no text, no watermarks"
    
    image_b64 = await yandex_art.generate(enhanced) if model == 'yandex' else await router_ai.generate_image_gemini(enhanced)
    
    if not image_b64:
        await message.answer(
            "❌ Ошибка генерации. Попробуйте другую модель или описание.",
            reply_markup=get_back_btn()
        )
        await state.clear()
        return
    
    try:
        image_bytes = base64.b64decode(image_b64)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name
        
        await message.answer_photo(
            photo=FSInputFile(tmp_path),
            caption=(
                f"✅ <b>Готово!</b>\n\n"
                f"🎨 <b>Модель:</b> {'Яндекс АРТ' if model == 'yandex' else 'Gemini Nano'}\n"
                f"📝 <b>Промпт:</b> <code>{user_prompt[:50]}...</code>"
            ),
            reply_markup=InlineKeyboardBuilder()
            .button(text="📝 Создать пост", callback_data=f"art_to_post:{user_prompt}")
            .button(text="🔄 Еще вариант", callback_data="visual_back")
            .button(text="◀️ Меню", callback_data="back_menu")
            .as_markup(),
            parse_mode="HTML"
        )
        os.unlink(tmp_path)
    except Exception as e:
        logger.error(f"Send error: {e}")
        await message.answer("❌ Ошибка отправки", reply_markup=get_back_btn())
    
    await state.clear()


@content_router.callback_query(F.data == "visual_back")
async def visual_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await visual_select_model(callback.message, state)


# === 📅 СЕРИЯ ПОСТОВ ===

async def series_start(message: Message, state: FSMContext):
    await message.answer(
        "📅 <b>Серия постов</b>\n\n"
        "Введите через запятую:\n"
        "<code>количество дней, тема</code>\n\n"
        "Пример: <code>7, перепланировка студии</code>",
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.ai_series)


@content_router.message(ContentStates.ai_series)
async def ai_series_handler(message: Message, state: FSMContext):
    text = message.text.strip()
    
    try:
        if ',' in text:
            parts = [p.strip() for p in text.split(',', 1)]
            days = int(parts[0])
            topic = parts[1]
        else:
            await message.answer("❌ Введите: число, тема")
            return
    except:
        await message.answer("❌ Неверный формат")
        return
    
    if days < 1 or days > 60:
        await message.answer("❌ Введите 1-60")
        return
    
    await message.answer(f"⏳ <b>Генерирую {days} постов...</b>", parse_mode="HTML")
    
    prompt = (
        f"Создай {days} постов для прогрева по теме «{topic}». "
        f"Перепланировки, недвижимость, экспертный контент.\n\n"
        f"Формат: День N: Заголовок\nТекст 80-120 слов\nПризыв к действию\n\n"
        f"Тон: профессиональный, экспертный, московское бюро перепланировок. Избегай клише 'уникальный дизайн' и 'за 3 дня'. Используй юридические термины (Жилищная инспекция, проект, МНИИТЭП). Добавь эмодзи."
    )
    
    result = await router_ai.generate(prompt, max_tokens=4000)
    
    if not result:
        await message.answer("❌ Ошибка генерации", reply_markup=get_back_btn())
        await state.clear()
        return
    
    post_id = await db.add_content_post(
        title=f"Серия {days} дней: {topic[:40]}",
        body=result,
        cta="",
        channel="series",
        status="draft"
    )
    
    await message.bot.send_message(
        chat_id=LEADS_GROUP_CHAT_ID,
        message_thread_id=THREAD_ID_DRAFTS,
        text=f"📅 <b>Серия {days} дней</b>\n\n<b>Тема:</b> {topic}\n\n{result[:1500]}...",
        parse_mode="HTML"
    )
    
    await message.answer(
        f"✅ <b>Серия готова!</b>\n"
        f"📊 {days} постов\n\n"
        f"<b>Сгенерировать обложки?</b>",
        reply_markup=InlineKeyboardBuilder()
        .button(text="🟣 Яндекс АРТ", callback_data=f"gen_series_img:yandex:{topic}:{days}")
        .button(text="🟡 Gemini Nano", callback_data=f"gen_series_img:gemini:{topic}:{days}")
        .button(text="❌ Нет", callback_data="back_menu")
        .as_markup(),
        parse_mode="HTML"
    )
    await state.clear()


@content_router.callback_query(F.data.startswith("gen_series_img:"))
async def generate_series_images(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    model = parts[1]
    topic = parts[2]
    days = int(parts[3])
    
    await callback.answer("🎨 Генерация...")
    await callback.message.edit_text(
        f"⏳ <b>Генерация {days} обложек...</b>",
        parse_mode="HTML"
    )
    
    for i in range(1, days + 1):
        art_prompt = f"{topic}, день {i}, перепланировка, professional interior, modern design, no text"
        
        await callback.message.answer(f"🎨 <b>День {i}...</b>", parse_mode="HTML")
        
        image_b64 = await yandex_art.generate(art_prompt) if model == 'yandex' else await router_ai.generate_image_gemini(art_prompt)
        
        if image_b64:
            image_bytes = base64.b64decode(image_b64)
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name
            
            await callback.message.answer_photo(
                photo=FSInputFile(tmp_path),
                caption=f"🎨 <b>День {i}</b> — {topic}",
                parse_mode="HTML"
            )
            os.unlink(tmp_path)
    
    await callback.message.answer("✅ <b>Все обложки готовы!</b>", reply_markup=get_back_btn(), parse_mode="HTML")


# === 📋 КОНТЕНТ-ПЛАН ===

async def plan_start(message: Message, state: FSMContext):
    await message.answer(
        "📋 <b>Контент-план</b>\n\n"
        "Введите через запятую:\n"
        "<code>дни, тема</code>\n\n"
        "Пример: <code>5, объединение кухни и гостиной</code>",
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.ai_plan)


@content_router.message(ContentStates.ai_plan)
async def ai_plan_handler(message: Message, state: FSMContext):
    text = message.text.strip()
    
    try:
        if ',' in text:
            parts = [p.strip() for p in text.split(',', 1)]
            days = int(parts[0])
            topic = parts[1]
        else:
            await message.answer("❌ Введите: дни, тема")
            return
    except:
        await message.answer("❌ Неверный формат")
        return
    
    if days < 1 or days > 30:
        await message.answer("❌ 1-30 дней")
        return
    
    await message.answer(f"⏳ <b>Создаю план на {days} дней...</b>", parse_mode="HTML")
    
    prompt = (
        f"Контент-план на {days} дней. Тема: «{topic}»\n"
        f"Перепланировки, согласование, дизайн.\n\n"
        f"Для каждого дня: заголовок, содержание (2-3 предл), формат (текст/фото/карусель).\n\n"
        f"Тон: профессиональный, экспертный, московское бюро перепланировок. Избегай клише 'уникальный дизайн' и 'за 3 дня'. Используй юридические термины (Жилищная инспекция, проект, МНИИТЭП)."
    )
    
    plan = await router_ai.generate(prompt, max_tokens=3000)
    
    if not plan:
        await message.answer("❌ Ошибка", reply_markup=get_back_btn())
        await state.clear()
        return
    
    await message.bot.send_message(
        chat_id=LEADS_GROUP_CHAT_ID,
        message_thread_id=THREAD_ID_CONTENT_PLAN,
        text=f"📋 <b>План {days} дней</b>\n\n<b>Тема:</b> {topic}\n\n{plan}",
        parse_mode="HTML"
    )
    
    await message.answer(
        f"✅ <b>План готов!</b>\n\n"
        f"<b>Сгенерировать арты?</b>",
        reply_markup=InlineKeyboardBuilder()
        .button(text="🟣 Яндекс АРТ", callback_data=f"gen_plan_img:yandex:{topic}:{days}")
        .button(text="🟡 Gemini Nano", callback_data=f"gen_plan_img:gemini:{topic}:{days}")
        .button(text="❌ Нет", callback_data="back_menu")
        .as_markup(),
        parse_mode="HTML"
    )
    await state.clear()


# === 📰 НОВОСТЬ ===

async def news_start(message: Message, state: FSMContext):
    await message.answer(
        "📰 <b>Экспертная новость</b>\n\n"
        "Введите тему:\n"
        "• Перепланировка — изменения в законе\n"
        "• Ипотека — ставки, программы\n"
        "• Строительство — новые технологии",
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.ai_news)


@content_router.message(ContentStates.ai_news)
async def ai_news_handler(message: Message, state: FSMContext):
    topic = message.text
    
    await message.answer("🔍 <b>Пишу новость...</b>", parse_mode="HTML")
    
    prompt = (
        f"Экспертная новость на тему «{topic}». "
        f"Структура: заголовок, суть новости, комментарий эксперта, "
        f"что значит для людей, призыв к консультации. "
        f"200-250 слов. Хештеги: #новость #недвижимость #TERION"
    )
    
    news = await router_ai.generate(prompt)
    
    if not news:
        await message.answer("❌ Ошибка", reply_markup=get_back_btn())
        await state.clear()
        return
    
    if VK_QUIZ_LINK not in news:
        news += f"\n\n📍 <a href='{VK_QUIZ_LINK}'>Пройти квиз</a> @terion_bot\n#TERION #перепланировка #москва"
    
    post_id = await show_preview(message, news)
    await state.set_state(ContentStates.preview_mode)
    await state.update_data(post_id=post_id, text=news)


# === 📝 БЫСТРЫЙ ТЕКСТ ===

async def quick_start(message: Message, state: FSMContext):
    await message.answer(
        "📝 <b>Быстрый текст</b>\n\n"
        "Введите тему:",
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.ai_text)


@content_router.message(ContentStates.ai_text)
async def ai_text_handler(message: Message, state: FSMContext):
    topic = message.text
    
    await message.answer("⏳ <b>Пишу...</b>", parse_mode="HTML")
    
    prompt = (
        f"Пост для TG на тему «{topic}». "
        f"Экспертный, живой стиль. 100-150 слов. "
        f"Эмодзи + призыв к консультации @terion_bot"
    )
    
    text = await router_ai.generate(prompt)
    
    if not text:
        await message.answer("❌ Ошибка", reply_markup=get_back_btn())
        await state.clear()
        return
    
    if VK_QUIZ_LINK not in text:
        text += f"\n\n📍 <a href='{VK_QUIZ_LINK}'>Пройти квиз</a> @terion_bot\n#TERION #перепланировка #москва"
    
    post_id = await show_preview(message, text)
    await state.set_state(ContentStates.preview_mode)
    await state.update_data(post_id=post_id, text=text)


# === ПУБЛИКАЦИЯ ===

import re


def clean_html_for_vk(text: str) -> str:
    """Очистка HTML-разметки для ВК"""
    # Удаляем теги <b>, </b>, <i>, </i>, <u>, </u>
    text = re.sub(r'</?b>', '', text)
    text = re.sub(r'</?i>', '', text)
    text = re.sub(r'</?u>', '', text)
    text = re.sub(r'</?strong>', '', text)
    text = re.sub(r'</?em>', '', text)
    # Удаляем <a href="...">...</a> - оставляем только текст ссылки
    text = re.sub(r'<a href="[^"]*">([^<]*)</a>', r'\1', text)
    # Удаляем остальные теги
    text = re.sub(r'</?[^>]+>', '', text)
    # Удаляем лишние переносы строк
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


async def send_post(bot: Bot, channel_id: int, post: dict, channel_name: str) -> tuple[bool, str]:
    """Отправка поста в канал и возврат результата"""
    text = post['body']
    if VK_QUIZ_LINK not in text:
        text += f"\n\n📍 <a href='{VK_QUIZ_LINK}'>Пройти квиз</a>"
    
    try:
        if post.get("image_url"):
            msg = await bot.send_photo(channel_id, post["image_url"], text, parse_mode="HTML")
        else:
            msg = await bot.send_message(channel_id, text, parse_mode="HTML")
        
        # Формируем ссылку на пост
        if msg.chat.username:
            link = f"https://t.me/{msg.chat.username}/{msg.message_id}"
        else:
            link = f"https://t.me/c/{str(channel_id).replace('-100', '')}/{msg.message_id}"
        
        return True, link
    except Exception as e:
        return False, str(e)


@content_router.callback_query(F.data.startswith("pub_terion:"))
async def publish_terion(callback: CallbackQuery, state: FSMContext):
    """Публикация только в TERION"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    if not post:
        await callback.answer("❌ Пост не найден")
        return
    
    await callback.answer("🚀 Публикую в TERION...")
    
    success, result = await send_post(callback.bot, CHANNEL_ID_TERION, post, "TERION")
    
    if success:
        await db.update_content_post(post_id, status="published")
        await callback.message.edit_text(
            f"✅ <b>Опубликовано в TERION</b>\n\n🔗 <a href='{result}'>Ссылка на пост</a>",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            f"❌ <b>Ошибка публикации в TERION</b>\n\n{result}",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
    
    await state.clear()


@content_router.callback_query(F.data.startswith("pub_dom_grnd:"))
async def publish_dom_grnd(callback: CallbackQuery, state: FSMContext):
    """Публикация только в ДОМ ГРАНД"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    if not post:
        await callback.answer("❌ Пост не найден")
        return
    
    await callback.answer("🚀 Публикую в ДОМ ГРАНД...")
    
    success, result = await send_post(callback.bot, CHANNEL_ID_DOM_GRAD, post, "ДОМ ГРАНД")
    
    if success:
        await db.update_content_post(post_id, status="published")
        await callback.message.edit_text(
            f"✅ <b>Опубликовано в ДОМ ГРАНД</b>\n\n🔗 <a href='{result}'>Ссылка на пост</a>",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            f"❌ <b>Ошибка публикации в ДОМ ГРАНД</b>\n\n{result}",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
    
    await state.clear()


@content_router.callback_query(F.data.startswith("pub_all:"))
async def publish_all(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    if not post:
        await callback.answer("❌ Пост не найден")
        return
    
    await callback.answer("🚀 Публикую...")
    
    text = post['body']
    if VK_QUIZ_LINK not in text:
        text += f"\n\n📍 <a href='{VK_QUIZ_LINK}'>Пройти квиз</a>"
    
    results = []
    
    # TG TERION
    try:
        if post.get("image_url"):
            await callback.bot.send_photo(CHANNEL_ID_TERION, post["image_url"], text, parse_mode="HTML")
        else:
            await callback.bot.send_message(CHANNEL_ID_TERION, text, parse_mode="HTML")
        results.append("✅ TERION TG")
    except Exception as e:
        results.append(f"❌ TERION: {e}")
    
    # TG ДОМ ГРАНД
    try:
        if post.get("image_url"):
            await callback.bot.send_photo(CHANNEL_ID_DOM_GRAD, post["image_url"], text, parse_mode="HTML")
        else:
            await callback.bot.send_message(CHANNEL_ID_DOM_GRAD, text, parse_mode="HTML")
        results.append("✅ ДОМ ГРАНД TG")
    except Exception as e:
        results.append(f"❌ ДОМ ГРАНД: {e}")
    
    # VK
    try:
        image_bytes = await download_photo(callback.bot, post["image_url"]) if post.get("image_url") else None
        vk_id = await vk_publisher.post_with_photo(text, image_bytes) if image_bytes else await vk_publisher.post_text_only(text)
        results.append(f"✅ VK (post{vk_id})" if vk_id else "❌ VK")
    except Exception as e:
        results.append(f"❌ VK: {e}")
    
    await db.update_content_post(post_id, status="published")
    
    # Лог
    await callback.bot.send_message(
        chat_id=LEADS_GROUP_CHAT_ID,
        message_thread_id=THREAD_ID_LOGS,
        text=f"🚀 <b>Публикация #{post_id}</b>\n\n" + "\n".join(results),
        parse_mode="HTML"
    )
    
    await callback.message.edit_text(
        f"✅ <b>Опубликовано!</b>\n\n" + "\n".join(results),
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )
    await state.clear()


# Подпись эксперта для постов
EXPERT_SIGNATURE = "\n\n---\n🏡 Эксперт: Юлия Пархоменко\nКомпания: TERION"


@content_router.callback_query(F.data.startswith("pub_tg:"))
async def publish_tg_only(callback: CallbackQuery, state: FSMContext):
    """Публикация в Telegram с подписью эксперта"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    if not post:
        await callback.answer("❌ Пост не найден")
        return
    
    # Добавляем подпись эксперта
    text = post['body']
    if VK_QUIZ_LINK not in text:
        text += f"\n\n📍 <a href='{VK_QUIZ_LINK}'>Пройти квиз</a>"
    text += EXPERT_SIGNATURE
    
    try:
        if post.get("image_url"):
            await callback.bot.send_photo(CHANNEL_ID_TERION, post["image_url"], text, parse_mode="HTML")
            await callback.bot.send_photo(CHANNEL_ID_DOM_GRAD, post["image_url"], text, parse_mode="HTML")
        else:
            await callback.bot.send_message(CHANNEL_ID_TERION, text, parse_mode="HTML")
            await callback.bot.send_message(CHANNEL_ID_DOM_GRAD, text, parse_mode="HTML")
        results = ["✅ TERION", "✅ ДОМ ГРАНД"]
    except Exception as e:
        results = [f"❌ {e}"]
    
    await db.update_content_post(post_id, status="published")
    await callback.message.edit_text(f"✅ <b>TG:</b>\n" + "\n".join(results), reply_markup=get_back_btn(), parse_mode="HTML")
    
    # Отправляем финансовый лог админу
    cost = 2.50  # Примерная стоимость
    await callback.bot.send_message(
        chat_id=LEADS_GROUP_CHAT_ID,
        text=f"💰 Пост #{post_id} опубликован в Telegram. Списано: {cost}₽"
    )
    
    await state.clear()


@content_router.callback_query(F.data.startswith("pub_vk:"))
async def publish_vk_only(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    # Очищаем HTML для ВК
    text = clean_html_for_vk(post['body'])
    if VK_QUIZ_LINK not in text:
        text += f"\n\n📍 Пройти квиз: {VK_QUIZ_LINK}"
    
    try:
        image_bytes = await download_photo(callback.bot, post["image_url"]) if post.get("image_url") else None
        vk_id = await vk_publisher.post_with_photo(text, image_bytes) if image_bytes else await vk_publisher.post_text_only(text)
        
        await db.update_content_post(post_id, status="published")
        
        vk_link = f"https://vk.com/wall-{VK_GROUP_ID}_{vk_id}" if vk_id else None
        if vk_link:
            await callback.message.edit_text(
                f"✅ <b>Опубликовано в VK</b>\n\n🔗 <a href='{vk_link}'>Ссылка на пост</a>",
                reply_markup=get_back_btn(),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text("❌ Ошибка VK", reply_markup=get_back_btn(), parse_mode="HTML")
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}", reply_markup=get_back_btn())
    
    await state.clear()


@content_router.callback_query(F.data.startswith("draft:"))
async def save_draft(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    try:
        if post.get("image_url"):
            await callback.bot.send_photo(LEADS_GROUP_CHAT_ID, post["image_url"], f"📝 <b>Черновик #{post_id}</b>\n\n{post['body']}", message_thread_id=THREAD_ID_DRAFTS, parse_mode="HTML")
        else:
            await callback.bot.send_message(LEADS_GROUP_CHAT_ID, f"📝 <b>Черновик #{post_id}</b>\n\n{post['body']}", message_thread_id=THREAD_ID_DRAFTS, parse_mode="HTML")
        
        await db.update_content_post(post_id, status="in_drafts")
        await callback.message.edit_text("✅ В черновиках (топик 85)", reply_markup=get_back_btn())
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}", reply_markup=get_back_btn())
    
    await state.clear()


@content_router.callback_query(F.data.startswith("edit:"))
async def edit_handler(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    if not post:
        await callback.answer("❌ Не найден")
        return
    
    await state.update_data(edit_post_id=post_id)
    await callback.message.answer(f"✏️ <b>Редактирование #{post_id}</b>\n\nТекущий текст:\n{post['body'][:500]}...\n\nВведите новый текст:", parse_mode="HTML")
    await callback.answer()
    await state.set_state(ContentStates.edit_post)


@content_router.message(ContentStates.edit_post)
async def edit_post_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    post_id = data.get("edit_post_id")
    
    if post_id:
        await db.update_content_post(post_id, body=message.text)
        await message.answer("✅ Обновлено!", reply_markup=get_back_btn())
    
    await state.clear()


@content_router.callback_query(F.data == "cancel")
async def cancel_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer("❌ Отменено")
    await state.clear()
    await callback.message.edit_text("❌ Отменено", reply_markup=get_back_btn())


@content_router.callback_query(F.data == "back_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("🎯 <b>TERION Content Bot</b>", reply_markup=get_back_btn(), parse_mode="HTML")

@content_router.callback_query(F.data.startswith("queue_img_"))
async def queue_img_handler(callback: CallbackQuery):
    post_id = int(callback.data.split("_")[-1])
    await callback.answer("🎨 Генерирую обложку для поста...")
    # Логика генерации и отправки превью
    from services.image_generator import image_generator
    from database import db
    
    post = await db.get_post_by_id(post_id)
    if post:
        image_bytes = await image_generator.generate_cover(post.get('title', 'Перепланировка'))
        if image_bytes:
            from aiogram.types import BufferedInputFile
            photo = BufferedInputFile(image_bytes, filename="cover.jpg")
            await callback.message.answer_photo(photo=photo, caption=f"🖼 Обложка для поста #{post_id}")
        else:
            await callback.message.answer("❌ Ошибка генерации")

@content_router.callback_query(F.data.startswith("queue_pub_"))
async def queue_pub_handler(callback: CallbackQuery):
    post_id = int(callback.data.split("_")[-1])
    await callback.answer("📢 Публикую пост...")
    from services.publisher import publisher
    from database import db
    
    post = await db.get_post_by_id(post_id)
    if post:
        results = await publisher.publish_all(post.get('text', ''))
        await callback.message.answer(f"✅ Опубликовано! Результаты: {results}")

@content_router.callback_query(F.data.startswith("queue_del_"))
async def queue_del_handler(callback: CallbackQuery):
    post_id = int(callback.data.split("_")[-1])
    from database import db
    # await db.delete_post(post_id) # Предполагаем наличие метода
    await callback.answer("🗑 Пост удален (имитация)")
    await callback.message.delete()


@content_router.message(ContentStates.photo_upload)
async def wrong_photo(message: Message):
    await message.answer("❌ Пожалуйста, отправьте фото или нажмите «Назад»")


@content_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🎯 <b>TERION Content Bot</b>\n\nСоздание и публикация контента:\n• Telegram (TERION + ДОМ ГРАНД)\n• ВКонтакте (с кнопками)\n\nВыберите действие:", reply_markup=get_main_menu(), parse_mode="HTML")
    await state.set_state(ContentStates.main_menu)
