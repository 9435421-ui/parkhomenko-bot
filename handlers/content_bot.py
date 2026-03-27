"""
Content Handler — GEORIS Ecosystem (RouterAI + YandexART Edition)
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

from database import db
from handlers.vk_publisher import VKPublisher
from agents.content_agent import ContentAgent
from config import (
    CONTENT_BOT_TOKEN,
    BOT_TOKEN,
    CHANNEL_ID_GEORIS,
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
)

logger = logging.getLogger(__name__)
content_router = Router()

# Папка шаблонов контента (редактируемые Юлией без правки кода)
_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "content")
_KNOWLEDGE_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge_base")

def _find_knowledge_for_topic(topic: str, max_chars: int = 3000) -> str:
    """Ищет релевантные файлы в базе знаний по теме и возвращает их содержимое."""
    if not os.path.exists(_KNOWLEDGE_BASE_DIR):
        return ""
    
    topic_lower = topic.lower()
    keywords = topic_lower.split()
    
    # Маппинг ключевых слов на папки/файлы
    topic_map = {
        "балкон": ["00_Общая_теория/Балконы_и_лоджии.md"],
        "лоджи": ["00_Общая_теория/Балконы_и_лоджии.md"],
        "общедомов": ["01_общедомовое_имущество"],
        "тсж": ["02_ТСЖ_и_согласования"],
        "согласован": ["06_Процедуры_и_документы/Согласовать_или_узаконить.md"],
        "узаконить": ["06_Процедуры_и_документы/Согласовать_или_узаконить.md"],
        "штраф": ["02_Кодексы_и_ответственность/Ответственность_собственника.md"],
        "старый фонд": ["02_Кодексы_и_ответственность/Старый_фонд_и_смешанные_перекрытия.md"],
        "коммерч": ["03_коммерческая_недвижимость"],
        "москв": ["04_Москва/ПП_Москвы_508_Правила_перепланировок.md"],
        "газ": ["03_Своды_правил_и_СП/СП_62_Газораспределительные_системы.md"],
        "окн": ["07_объекты_культурного_наследия_ОКН"],
        "памятник": ["07_объекты_культурного_наследия_ОКН"],
    }
    
    files_to_read = []
    for kw, paths in topic_map.items():
        if kw in topic_lower:
            for path in paths:
                full_path = os.path.join(_KNOWLEDGE_BASE_DIR, path)
                if os.path.isfile(full_path):
                    files_to_read.append(full_path)
                elif os.path.isdir(full_path):
                    # Берём первые 2 файла из папки
                    for f in sorted(os.listdir(full_path))[:2]:
                        if f.endswith('.md'):
                            files_to_read.append(os.path.join(full_path, f))
    
    if not files_to_read:
        # Общий поиск по всем файлам
        for root, dirs, files in os.walk(_KNOWLEDGE_BASE_DIR):
            dirs[:] = [d for d in dirs if 'venv' not in d]
            for f in files:
                if f.endswith('.md'):
                    fname_lower = f.lower().replace('_', ' ')
                    if any(kw in fname_lower for kw in keywords if len(kw) > 3):
                        files_to_read.append(os.path.join(root, f))
    
    result = []
    total_chars = 0
    for fpath in files_to_read[:3]:  # Максимум 3 файла
        try:
            text = open(fpath, encoding='utf-8').read()
            if total_chars + len(text) > max_chars:
                text = text[:max_chars - total_chars]
            result.append(f"--- {os.path.basename(fpath)} ---\n{text}")
            total_chars += len(text)
            if total_chars >= max_chars:
                break
        except Exception:
            pass
    
    return "\n\n".join(result)


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
    default = "\n\n---\n🏡 Эксперт: Юлия Пархоменко\nКомпания: GEORIS"
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

# ГЛОБАЛЬНЫЕ ОБРАБОТЧИКИ МЕНЮ (всегда активны)
@content_router.message(F.text.in_([
    "📸 Фото → Описание → Пост",
    "🎨 ИИ-Визуал",
    "✨ Креатив",
    "📰 Новость",
    "📋 План",
    "📝 Быстрый текст",
    "💡 Интересный факт",
    "🎉 Праздник РФ"
]))
async def global_menu_handler(message: Message, state: FSMContext):
    """Глобальный обработчик меню — работает из любого состояния"""
    await state.clear()  # Сбрасываем FSM
    
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
    edit_draft = State()       # Редактирование черновика
    quick_text = State()
    holiday_rf = State()       # Поздравление с официальным праздником РФ
    ai_text = State()
    ai_series = State()
    schedule_series = State()
    ai_visual_select = State()
    ai_news = State()
    ai_news_choose = State()
    ai_fact_choose = State()
    edit_post = State()


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
        op_base = "https://llm.api.cloud.yandex.net"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{op_base}/foundationModels/v1/imageGenerationAsync",
                    headers=self.headers,
                    json=payload
                ) as resp:
                    body = await resp.text()
                    if resp.status != 200:
                        logger.error(f"YandexART HTTP {resp.status}: {body[:300]}")
                        return None
                    try:
                        data = json.loads(body)
                    except Exception:
                        logger.error(f"YandexART invalid JSON: {body[:200]}")
                        return None
                    op_id = data.get("id")
                    if not op_id:
                        logger.warning(f"YandexART no operation id in response: {list(data.keys())}")
                        return None
                    # Polling результата (документация Yandex: operations на llm.api)
                    for _ in range(30):
                        await asyncio.sleep(2)
                        async with session.get(f"{op_base}/operations/{op_id}", headers=self.headers) as check:
                            if check.status != 200:
                                continue
                            result = await check.json()
                            if not result.get("done"):
                                continue
                            resp_obj = result.get("response") or {}
                            img_b64 = resp_obj.get("image")
                            if img_b64:
                                return img_b64
                            if result.get("error"):
                                logger.error(f"YandexART operation error: {result.get('error')}")
                                return None
                            logger.warning(f"YandexART done but no image in response: {list(resp_obj.keys())}")
                            return None
            logger.error("YandexART timeout waiting for image")
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
        model: str = "openai/gpt-4o",
        max_tokens: int = 2000,
        system_prompt: Optional[str] = None,
    ) -> Optional[str]:
        """Генерация текста. system_prompt задаёт роль/стиль модели."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
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
                        error_text = await resp.text()
                        error_msg = f"RouterAI HTTP {resp.status}: {error_text[:500]}"
                        logger.error(error_msg)
                        # Пробрасываем ошибку для обработки в вызывающем коде
                        raise Exception(error_msg)
        except Exception as e:
            error_msg = f"RouterAI error: {str(e)}"
            logger.error(error_msg)
            # Пробрасываем ошибку для обработки в вызывающем коде
            raise Exception(error_msg)
    
    async def generate_response(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 2000,
    ) -> Optional[str]:
        """Алиас для generate с другим порядком параметров (совместимость с utils/router_ai.py)"""
        return await self.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        )
    
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
            "max_tokens": 2000  # Увеличено до 2000
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
        """Генерация изображения через Flux.2-pro (Router AI)"""
        payload = {
            "model": "black-forest-labs/flux.2-pro",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://routerai.ru/api/v1/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        images = data["choices"][0]["message"].get("images", [])
                        if images:
                            url = images[0]["image_url"]["url"]
                            if "base64," in url:
                                return url.split("base64,")[1]
                        logger.error("Flux: no images in response")
                        return None
                    else:
                        error = await resp.text()
                        logger.error(f"Flux error {resp.status}: {error[:200]}")
                        return None
        except Exception as e:
            logger.error(f"Flux exception: {e}")
            return None


# Инициализация
yandex_art = YandexArtClient(YANDEX_API_KEY, FOLDER_ID)
router_ai = RouterAIClient(ROUTER_AI_KEY)


async def _auto_generate_image(prompt: str) -> Optional[str]:
    """Автоматический выбор модели генерации изображения.

    Приоритет по качеству и доступности:
      1. Яндекс АРТ  — лучшее качество, 10-30 с
      2. Router AI (Gemini Nano) — быстрее, ~5-10 с
      3. ImageGenerator (DALL-E / OpenRouter) — запасной вариант
    Возвращает base64-строку или None при полном отказе всех сервисов.
    """
    # 1. Flux.2-pro (Router AI) — лучшее качество
    try:
        image_b64 = await router_ai.generate_image_gemini(prompt)
        if image_b64:
            logger.info("Image: Flux.2-pro OK")
            return image_b64
    except Exception as e:
        logger.warning(f"Flux failed: {e}")
    # 2. Яндекс АРТ — fallback
    try:
        image_b64 = await yandex_art.generate(prompt)
        if image_b64:
            logger.info("Image: Yandex ART fallback OK")
            return image_b64
    except Exception as e:
        logger.warning(f"Yandex ART failed: {e}")
    # 3. ImageGenerator (OpenRouter DALL-E)
    # 3. ImageGenerator (OpenRouter DALL-E)
    try:
        from services.image_generator import image_generator
        image_bytes = await image_generator.generate_cover(prompt)
        if image_bytes:
            logger.info("Image: ImageGenerator fallback OK")
            return base64.b64encode(image_bytes).decode()
    except Exception as e:
        logger.warning(f"ImageGenerator fallback failed: {e}")

    return None


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
            consult_link = "https://t.me/georis_bot?start=consult"
        
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
    builder.button(text="🚀 GEORIS", callback_data=f"pub_georis:{post_id}")
    builder.button(text="🏘 ДОМ ГРАНД", callback_data=f"pub_dom_grnd:{post_id}")
    builder.button(text="📱 MAX", callback_data=f"pub_max:{post_id}")
    builder.button(text="🌐 VK", callback_data=f"pub_vk:{post_id}")
    builder.button(text="🗑 В черновики", callback_data=f"draft:{post_id}")
    builder.button(text="✏️ Редактировать", callback_data=f"edit:{post_id}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1, 2, 2, 1, 1, 1)
    return builder.as_markup()


def get_queue_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """Кнопки для черновиков в рабочей группе: GEORIS, ДОМ ГРАНД, MAX, VK, Во все каналы."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📤 Во все каналы", callback_data=f"pub_all:{post_id}")
    builder.button(text="🚀 GEORIS", callback_data=f"pub_georis:{post_id}")
    builder.button(text="🏘 ДОМ ГРАНД", callback_data=f"pub_dom_grnd:{post_id}")
    builder.button(text="📱 MAX", callback_data=f"pub_max:{post_id}")
    builder.button(text="🌐 VK", callback_data=f"pub_vk:{post_id}")
    builder.button(text="⏰ Запланировать", callback_data=f"schedule:{post_id}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1, 2, 2, 1, 1)
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
    """
    Загрузка фото: поддерживает URL (http/https) и file_id от Telegram.
    - Если file_id начинается с http - качаем как файл
    - Иначе - запрашиваем через bot.get_file
    """
    try:
        # Проверяем, если это URL
        if file_id.startswith("http://") or file_id.startswith("https://"):
            async with aiohttp.ClientSession() as session:
                async with session.get(file_id) as resp:
                    if resp.status == 200:
                        return await resp.read()
                    else:
                        logger.error(f"HTTP download failed: {resp.status}")
                        return None
        
        # Иначе - file_id от Telegram
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


async def _photo_input_for_send(bot: Bot, image_url: str):
    """
    Для send_photo: если image_url — http(s) ссылка, скачиваем и возвращаем BufferedInputFile,
    иначе возвращаем file_id (Telegram не принимает битые/временные URL).
    Возвращает (photo=...) для вызова bot.send_photo(chat_id, photo=..., caption=...).
    """
    if not image_url:
        return None
    if image_url.startswith("http://") or image_url.startswith("https://"):
        data = await download_photo(bot, image_url)
        if data:
            return BufferedInputFile(data, filename="post.jpg")
        logger.error("Не удалось скачать фото по URL, пропуск изображения")
        return None
    return image_url  # file_id — передаём как есть


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


def _build_cover_prompt(text: str, topic: str = "") -> str:
    """Строит промпт обложки по теме и тексту поста."""
    import re
    clean = re.sub(r"<[^>]+>", "", text).lower()
    t = (topic + " " + clean).lower()

    parts: list[str] = []
    if any(w in t for w in ["газ", "газовая плита", "газ плит"]):
        parts.append("modern kitchen with gas stove, stylish Moscow apartment")
    if any(w in t for w in ["перепланировк", "снос стен", "объединени", "проем", "демонтаж"]):
        parts.append("apartment renovation open space planning modern interior Moscow")
    if any(w in t for w in ["кухн", "гостин", "студи", "зонирован"]):
        parts.append("luxury kitchen living room open plan Moscow apartment")
    if any(w in t for w in ["ванн", "санузл", "bathroom"]):
        parts.append("modern bathroom spa renovation Moscow")
    if any(w in t for w in ["мжи", "согласован", "документ", "бти"]):
        parts.append("architectural office blueprints professional workspace Moscow")
    if any(w in t for w in ["дизайн", "интерьер", "минимализм"]):
        parts.append("luxury interior design minimalist Moscow apartment")
    if any(w in t for w in ["новостройк", "жк", "апартамент", "студия"]):
        parts.append("modern Moscow new building apartment interior")
    if any(w in t for w in ["инвест", "стоимост", "цена", "продажа"]):
        parts.append("luxury Moscow real estate investment property")

    base = ", ".join(parts) if parts else "modern luxury Moscow apartment interior minimalist style"
    return (
        f"Professional architectural photography, {base}, "
        "high quality photorealistic render, 4K, natural lighting, wide angle. "
        "No text, no words, no letters, no watermarks — image only."
    )


async def show_preview(message: Message, text: str, image_file_id: Optional[str] = None, post_id: Optional[int] = None):
    """Показывает превью поста. Если изображение не передано — генерирует автоматически."""
    if not post_id:
        post_id = await db.add_content_post(
            title="Preview",
            body=text,
            cta="",
            image_url=image_file_id,
            channel="preview",
            status="preview"
        )

    caption = f"👁 <b>Предпросмотр</b>\n\n{text[:3000]}"

    if not image_file_id:
        # Авто-генерация обложки по теме поста
        status_msg = await message.answer("🎨 <b>Генерирую обложку...</b>", parse_mode="HTML")
        prompt = _build_cover_prompt(text)
        image_b64 = await _auto_generate_image(prompt)
        try:
            await status_msg.delete()
        except Exception:
            pass

        if image_b64:
            try:
                image_bytes = base64.b64decode(image_b64)
                photo_input = BufferedInputFile(image_bytes, filename="cover.jpg")
                sent = await message.answer_photo(
                    photo=photo_input,
                    caption=caption,
                    reply_markup=get_preview_keyboard(post_id, True),
                    parse_mode="HTML"
                )
                # Сохраняем file_id в БД, чтобы использовать при публикации
                if sent.photo:
                    await db.update_content_plan_entry(post_id, image_url=sent.photo[-1].file_id)
                return post_id
            except Exception as e:
                logger.warning(f"Auto-image preview failed: {e}")

    # Fallback — превью без картинки (или с переданным изображением)
    kb = get_preview_keyboard(post_id, bool(image_file_id))
    if image_file_id:
        await message.answer_photo(photo=image_file_id, caption=caption, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(caption, reply_markup=kb, parse_mode="HTML")
    return post_id


# === 📸 ФОТО WORKFLOW ===

async def photo_start(message: Message, state: FSMContext):
    await message.answer(
        "📸 <b>Фото → Пост</b>\n\n"
        "Загрузите фото — интерьер, планировку или ремонт.\n"
        "Бот сам проанализирует и напишет экспертный пост.",
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.photo_upload)


@content_router.message(ContentStates.photo_upload, F.photo)
async def process_photo(message: Message, state: FSMContext):
    photo = message.photo[-1]
    file_id = photo.file_id
    
    await message.answer(f"🔍 <b>Анализирую фото...</b>", parse_mode="HTML")
    
    image_bytes = await download_photo(message.bot, file_id)
    if not image_bytes:
        await message.answer("❌ Ошибка загрузки", reply_markup=get_back_btn())
        await state.clear()
        return
    
    compressed = await compress_image(image_bytes, max_size=1024)
    image_b64 = base64.b64encode(compressed).decode()
    
    prompt = (
        "Ты — ведущий эксперт GEORIS по перепланировке квартир в Москве.\n\n"
        "Задача: проанализируй фото и напиши готовый экспертный пост для Telegram.\n\n"
        "1. Определи что на фото: интерьер, планировка, ремонт, демонтаж\n"
        "2. Напиши экспертный пост 150-200 слов\n"
        "3. Используй термины по смыслу: МЖИ, трассировка, СНиП\n"
        "4. В конце: призыв обратиться в GEORIS на консультацию\n"
        "5. Эмодзи 3-5 штук\n"
        "6. НЕ вставляй ссылки — только текст"
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
            f"#перепланировка #георис"
        )
    
    if VK_QUIZ_LINK not in description:
        description += f"\n\n📍 <a href='{VK_QUIZ_LINK}'>Пройти квиз</a> @georis_bot\n#GEORIS #перепланировка #москва"
    
    post_id = await db.add_content_post(
        title=f"Фото-анализ: экспертный пост",
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
    """Запускает генерацию изображения — сразу спрашивает промпт."""
    await message.answer(
        "🎨 <b>Генерация изображения</b>\n\n"
        "Введите описание сцены или интерьера:\n\n"
        "Примеры:\n"
        "• Скандинавская гостиная с панорамными окнами\n"
        "• Современная кухня-студия, минимализм\n"
        "• Перепланировка в сталинке, до/после\n\n"
        "<i>Система автоматически выберет лучшую доступную модель.</i>",
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.ai_visual_prompt)


@content_router.callback_query(F.data.startswith("visual_model:"))
async def visual_model_selected(callback: CallbackQuery, state: FSMContext):
    """Совместимость со старыми кнопками — перенаправляет на авто-режим."""
    await callback.answer()
    await callback.message.edit_text(
        "🎨 <b>Генерация изображения</b>\n\n"
        "Введите описание:\n\n"
        "Примеры:\n"
        "• Скандинавская гостиная с панорамными окнами\n"
        "• Современная кухня-студия, минимализм\n"
        "• Перепланировка в сталинке, до/после",
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.ai_visual_prompt)


@content_router.message(ContentStates.ai_visual_prompt)
async def ai_visual_handler(message: Message, state: FSMContext):
    user_prompt = message.text or ""

    await message.answer("⏳ <b>Генерирую изображение...</b>", parse_mode="HTML")

    enhanced = (
        f"{user_prompt}, professional architectural photography, interior design, "
        "high quality, detailed. No text, no words, no letters, no captions, no watermarks — image only."
    )

    image_b64 = await _auto_generate_image(enhanced)

    if not image_b64:
        await message.answer(
            "❌ Все сервисы недоступны. Попробуйте позже или измените описание.",
            reply_markup=get_back_btn()
        )
        await state.clear()
        return

    try:
        image_bytes = base64.b64decode(image_b64)
        photo = BufferedInputFile(image_bytes, filename="visual.jpg")
        
        # ── ВОССТАНОВЛЕНИЕ ЦЕПОЧКИ: Сохраняем file_id и prompt в FSM ───────────────
        sent_message = await message.answer_photo(
            photo=photo,
            caption=(
                f"✅ <b>Готово!</b>\n\n"
                f"📝 <b>Промпт:</b> <code>{user_prompt[:80]}</code>"
            ),
            reply_markup=InlineKeyboardBuilder()
            .button(text="📝 Создать пост", callback_data="art_to_post:gen")
            .button(text="🔄 Ещё вариант", callback_data="visual_back")
            .button(text="◀️ Меню", callback_data="back_menu")
            .as_markup(),
            parse_mode="HTML"
        )
        
        # Сохраняем file_id и prompt в состояние FSM для использования в art_to_post_handler
        if sent_message.photo:
            file_id = sent_message.photo[-1].file_id  # Берем самое большое фото
            await state.update_data(
                visual_file_id=file_id,
                visual_prompt=user_prompt,
                visual_image_bytes=image_b64  # Сохраняем base64 для возможного использования
            )
            logger.debug(f"✅ Сохранены в FSM: file_id={file_id[:20]}..., prompt={user_prompt[:30]}...")
        
    except Exception as e:
        logger.error(f"Send visual error: {e}")
        await message.answer("❌ Ошибка отправки изображения", reply_markup=get_back_btn())

    # НЕ очищаем state - оставляем данные для art_to_post_handler


@content_router.callback_query(F.data == "visual_back")
async def visual_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await visual_select_model(callback.message, state)


@content_router.callback_query(F.data.startswith("art_to_post:"))
async def art_to_post_handler(callback: CallbackQuery, state: FSMContext):
    """Создаёт полноценный пост из сгенерированного изображения."""
    topic = callback.data.split(":", 1)[1]
    await callback.answer()
    await callback.message.answer("✍️ <b>Пишу пост по теме изображения...</b>", parse_mode="HTML")

    # ── ВОССТАНОВЛЕНИЕ ЦЕПОЧКИ: Используем сохраненные file_id и prompt из FSM ──────
    state_data = await state.get_data()
    file_id = state_data.get("visual_file_id")
    saved_prompt = state_data.get("visual_prompt", topic)
    image_b64 = state_data.get("visual_image_bytes")
    
    # Используем сохраненный prompt или topic из callback
    actual_topic = saved_prompt if saved_prompt else topic

    prompt = (
        f"Напиши экспертный пост для Telegram-канала по перепланировкам (GEORIS).\n\n"
        f"Тема изображения: «{actual_topic}»\n\n"
        f"Структура:\n"
        f"1) Цепляющий заголовок с эмодзи\n"
        f"2) 2-3 абзаца экспертного контента (400-500 знаков)\n"
        f"3) Призыв: 👉 Записаться на консультацию: @Parkhovenko_i_kompaniya_bot\n\n"
        f"Используй термины: МЖИ, несущие стены, трассировка, СНиП. Без общих фраз."
    )
    text = None
    error_message = None
    try:
        text = await router_ai.generate_response(
            user_prompt=prompt,
            max_tokens=2000,  # Увеличено до 2000
        )
    except Exception as e:
        error_message = str(e)
        logger.error("photo_to_post: router_ai error: %s", e)
        # Отправляем ошибку в топик "Логи"
        try:
            from aiogram import Bot
            from aiogram.client.default import DefaultBotProperties
            bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            await bot.send_message(
                LEADS_GROUP_CHAT_ID,
                f"⚠️ <b>Ошибка нейросети</b>\n\n"
                f"Тема: <code>{actual_topic[:100]}</code>\n"
                f"Ошибка: <code>{error_message[:500]}</code>",
                message_thread_id=THREAD_ID_LOGS,
            )
            await bot.session.close()
        except Exception as notify_err:
            logger.error("Не удалось отправить ошибку в топик: %s", notify_err)
    
    if not text:
        text = (
            f"<b>🏠 Перепланировка по теме: {actual_topic}</b>\n\n"
            f"Каждый объект уникален. Правильный подход — согласование с МЖИ, "
            f"расчёт несущих конструкций и трассировка изменений по СНиП.\n\n"
            f"👉 Записаться на консультацию: @Parkhovenko_i_kompaniya_bot"
        )

    # Сохраняем file_id и prompt для использования при публикации
    await state.update_data(
        post_text=text,
        post_image_file_id=file_id,
        post_image_b64=image_b64,
        post_topic=actual_topic
    )

    await show_preview(callback.message, text)
    await state.set_state(ContentStates.preview_mode)


# === 📅 СЕРИЯ ПОСТОВ ===

async def series_start(message: Message, state: FSMContext):
    await message.answer(
        "✨ <b>Креатив — Тренды</b>\n\n"
        "Введите тему — я найду актуальные тренды и адаптирую под GEORIS:\n\n"
        "Примеры:\n"
        "• <code>перепланировка квартиры</code>\n"
        "• <code>маленькие квартиры</code>\n"
        "• <code>ремонт новостройки</code>\n\n"
        "<i>Или укажите количество: <code>5, перепланировка</code></i>",
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.ai_series)


@content_router.message(ContentStates.ai_series)
async def ai_series_handler(message: Message, state: FSMContext):
    """Генерирует серию постов и разбивает их на отдельные черновики с обложками."""
    text = message.text.strip()
    
    if ',' in text:
        try:
            parts = [p.strip() for p in text.split(',', 1)]
            days = int(parts[0])
            topic = parts[1]
            if days < 1 or days > 60:
                await message.answer("❌ Введите 1-60")
                return
        except:
            await message.answer("❌ Неверный формат. Пример: <code>5, ремонт новостройки</code>", parse_mode="HTML")
            return
    else:
        # Авторежим — только тема, ИИ выбирает количество
        topic = text
        await message.answer("🔍 <b>Анализирую тренды по теме...</b>", parse_mode="HTML")
        try:
            import json, re
            analysis = await router_ai.generate_response(
                user_prompt=(
                    f"Тема: {topic}. GEORIS - перепланировка квартир в Москве. "
                    f"Предложи количество трендовых постов (5-10) и форматы. "
                    '{"days": 7, "formats": ["до/после", "миф", "кейс"]}'
                ),
                system_prompt="Отвечай только валидным JSON без пояснений.",
                max_tokens=200,
            )
            json_match = re.search(r'\{.*\}', analysis, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                days = data.get("days", 7)
            else:
                days = 7
        except Exception as e:
            logger.error(f"ai_series_handler: ошибка анализа: {e}")
            days = 7

    await message.answer(f"⏳ <b>Генерирую {days} трендовых постов...</b>", parse_mode="HTML")

    cases_content = _load_content_template("expert_cases.txt", "МЖИ, несущие стены, трассировка, акты скрытых работ.")
    kb_content = _find_knowledge_for_topic(topic)
    if kb_content:
        cases_content = kb_content + "\n\n" + cases_content
    prompt_default = (
        "Роль: Контент-стратег GEORIS (перепланировка квартир в Москве).\n"
        "Задача: создай {days} трендовых постов по теме «{topic}» для Telegram-канала.\n\n"
        "ТРЕНДЫ 2025 в контенте про недвижимость и ремонт:\n"
        "- Формат 'до/после' с конкретными цифрами (было 32м², стало 45м² по ощущению)\n"
        "- Разоблачение мифов ('3 мифа о несущих стенах')\n"
        "- Реальные кейсы с болями клиентов и happy end\n"
        "- Провокационные вопросы ('А вы знали что это незаконно?')\n"
        "- Сравнения ('Перепланировка vs новая квартира — что выгоднее?')\n"
        "- Лайфхаки с конкретными советами\n\n"
        "Экспертная база:\n{cases}\n\n"
        "Формат КАЖДОГО дня:\n"
        "День N | [тип тренда]\n"
        "Текст 150-200 слов, живой язык, эмодзи 3-5 штук.\n"
        "В конце: призыв в GEORIS на консультацию.\n"
        "БЕЗ клише 'уникальный', 'профессиональный подход', 'за 3 дня'."
    )
    prompt_tpl = _load_content_template("series_warmup_prompt.txt", prompt_default)
    try:
        prompt = prompt_tpl.format(days=days, topic=topic, cases=cases_content)
    except KeyError:
        prompt = prompt_default.format(days=days, topic=topic, cases=cases_content)
    if "{cases}" in prompt:
        prompt = prompt.replace("{cases}", cases_content)

    result = None
    error_message = None
    try:
        result = await router_ai.generate_response(
            user_prompt=prompt,
            max_tokens=2000,
        )
    except Exception as e:
        error_message = str(e)
        logger.error("ai_series_handler: router_ai error: %s", e)
        try:
            from aiogram import Bot
            from aiogram.client.default import DefaultBotProperties
            bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            await bot.send_message(
                LEADS_GROUP_CHAT_ID,
                f"⚠️ <b>Ошибка нейросети</b>\n\n"
                f"Серия: <code>{days} дней, {topic[:100]}</code>\n"
                f"Ошибка: <code>{error_message[:500]}</code>",
                message_thread_id=THREAD_ID_LOGS,
            )
            await bot.session.close()
        except Exception as notify_err:
            logger.error("Не удалось отправить ошибку в топик: %s", notify_err)
    
    if not result:
        await message.answer(
            f"⚠️ <b>Ошибка генерации</b>\n\n{error_message[:200] if error_message else 'Попробуйте ещё раз.'}",
            reply_markup=get_back_btn(),
            parse_mode="HTML",
        )
        await state.clear()
        return

    # ── НОВОЕ: Парсим результат по дням и создаём отдельные черновики ──
    await message.answer(f"📝 <b>Создаю {days} черновиков с обложками...</b>", parse_mode="HTML")
    
    # Парсим текст по паттерну "День N:" или "День N |"
    import re
    day_pattern = r"(?:День|день)\s+(\d+)\s*[:|](.+?)(?=(?:День|день)\s+\d+|$)"
    day_matches = re.findall(day_pattern, result, re.DOTALL | re.IGNORECASE)
    
    created = 0
    errors = 0
    
    for i in range(1, days + 1):
        try:
            # Находим текст для этого дня из спарсенного результата
            day_text = None
            for match_day, match_text in day_matches:
                if int(match_day) == i:
                    day_text = match_text.strip()
                    break
            
            # Если не нашли в парсе, используем ИИ для генерации текста для этого конкретного дня
            if not day_text:
                format_sample = ["до/после", "миф", "кейс", "вопрос", "факт", "совет"][i % 6]
                day_text = await router_ai.generate_response(
                    user_prompt=(
                        f"Напиши готовый Telegram-пост для компании GEORIS (перепланировка квартир в Москве).\n"
                        f"Тема: {topic}. День {i}/{days}. Формат: {format_sample}.\n"
                        f"Требования: 150-200 слов, живой язык, эмодзи 3-5 штук, в конце призыв на консультацию. "
                        f"БЕЗ пояснений, только готовый пост."
                    ),
                    max_tokens=400,
                )
            
            if not day_text:
                logger.error(f"ai_series_handler: не удалось получить текст дня {i}")
                errors += 1
                continue
            
            # 1. Генерируем обложку
            post_excerpt = day_text[:150].replace('"', '').replace("'", '').strip()
            art_prompt = (
                f"{post_excerpt}. "
                "Moscow apartment interior, professional architectural visualization, "
                "modern realistic render, bright natural light. "
                "No text, no words, no letters, no watermarks - image only."
            )
            image_b64 = await _auto_generate_image(art_prompt)
            image_file_id = None
            
            if image_b64:
                try:
                    image_bytes = base64.b64decode(image_b64)
                    photo = BufferedInputFile(image_bytes, filename=f"series_day_{i}.jpg")
                    sent = await message.bot.send_photo(
                        chat_id=LEADS_GROUP_CHAT_ID,
                        message_thread_id=THREAD_ID_DRAFTS,
                        photo=photo,
                        caption=f"📅 День {i}: {topic}",
                    )
                    image_file_id = sent.photo[-1].file_id
                except Exception as e:
                    logger.error(f"ai_series_handler: ошибка обложки дня {i}: {e}")
            
            # 2. Применяем квиз и хэштеги
            post_text_full = ensure_quiz_and_hashtags(day_text)
            
            # 3. Сохраняем черновик в БД
            post_id = await db.add_content_post(
                title=f"День {i}: {topic}",
                body=post_text_full,
                cta="",
                channel="draft",
                status="draft",
                image_url=image_file_id,
                theme=topic,
            )
            created += 1
            
            # 4. Анонс в топик 85 с кнопками
            try:
                kb = InlineKeyboardBuilder()
                kb.button(text="📤 Во все каналы", callback_data=f"pub_all:{post_id}")
                kb.button(text="⏰ Запланировать", callback_data=f"schedule:{post_id}")
                kb.button(text="📤 TG", callback_data=f"pub_tg:{post_id}")
                kb.button(text="📘 VK", callback_data=f"pub_vk:{post_id}")
                kb.button(text="✏️ Редактировать", callback_data=f"edit_draft:{post_id}")
                kb.adjust(2)
                draft_preview = post_text_full[:600] + ("..." if len(post_text_full) > 600 else "")
                await message.bot.send_message(
                    chat_id=LEADS_GROUP_CHAT_ID,
                    message_thread_id=THREAD_ID_DRAFTS,
                    text=f"<b>День {i}/{days}</b> — {topic}\n\n{draft_preview}",
                    reply_markup=kb.as_markup(),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error(f"ai_series_handler: ошибка топика дня {i}: {e}")
        
        except Exception as e:
            logger.error(f"ai_series_handler: ошибка дня {i}: {e}")
            errors += 1
    
    # ── Финальное сообщение ──
    await message.answer(
        ("✅" if errors == 0 else "⚠️") + f" <b>Готово!</b>\n\nСоздано черновиков: <b>{created}/{days}</b>\nОшибок: <b>{errors}</b>\n\nЧерновики с обложками — в топике Черновики",
        reply_markup=get_back_btn(),
        parse_mode="HTML",
    )
    await state.clear()


# === 📋 КОНТЕНТ-ПЛАН ===

_PLAN_SYSTEM = (
    "Ты — контент-стратег компании GEORIS (перепланировки квартир в Москве).\n"
    "Создай редакционный контент-план для Telegram-канала. Требования:\n"
    "— Для каждого дня: тип поста, заголовок/тема, ключевое сообщение (1 предложение), формат (текст / фото / карусель / видео)\n"
    "— Чередуй форматы: экспертный пост, живая история клиента, интересный факт, вопрос аудитории, новость/тренд\n"
    "— Темы должны логично вытекать одна из другой и прогревать аудиторию\n"
    "— Тон: человечный, без казённого языка\n"
    "— ЗАПРЕЩЕНО: жёсткие технические чек-листы, перечисление СНиПов, схемы согласования\n"
    "— Формат вывода:\n"
    "День N | [Тип] | Заголовок\n"
    "Идея: ...\n"
    "Формат: ...\n"
)


async def plan_start(message: Message, state: FSMContext):
    await message.answer(
        "📋 <b>Контент-план</b>\n\n"
        "Введите тему — я сам предложу структуру и количество постов:\n\n"
        "Примеры:\n"
        "• <code>перепланировка квартиры</code>\n"
        "• <code>ипотека и недвижимость</code>\n"
        "• <code>дизайн маленьких квартир</code>\n\n"
        "<i>Или укажите количество дней вручную: <code>7, перепланировка</code></i>",
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.ai_plan)


@content_router.message(ContentStates.ai_plan)
async def ai_plan_handler(message: Message, state: FSMContext):
    text = message.text.strip()
    days = None
    topic = None

    if ',' in text:
        # Ручной режим: "7, перепланировка"
        try:
            parts = [p.strip() for p in text.split(',', 1)]
            days = int(parts[0])
            topic = parts[1]
            if days < 1 or days > 30:
                await message.answer("❌ Укажите от 1 до 30 дней")
                return
            await message.answer(f"⏳ <b>Составляю контент-план на {days} дней...</b>", parse_mode="HTML")
        except Exception:
            await message.answer("❌ Неверный формат. Пример: <code>7, перепланировка</code>", parse_mode="HTML")
            return
    else:
        # Авто режим: только тема — ИИ предлагает структуру
        topic = text
        await message.answer(f"🔍 <b>Анализирую тему...</b>", parse_mode="HTML")

        analysis_prompt = (
            f"Ты — контент-стратег компании GEORIS (перепланировка квартир в Москве).\n"
            f"Пользователь хочет создать серию постов на тему: «{topic}»\n\n"
            f"Задача: предложи оптимальную структуру контент-плана.\n"
            f"Ответь СТРОГО в формате JSON без пояснений:\n"
            f'{{"days": 7, "posts": [{{"day": 1, "title": "Название поста", "format": "экспертный совет"}}, ...]}}'
        )

        try:
            analysis = await router_ai.generate_response(
                user_prompt=analysis_prompt,
                system_prompt="Отвечай только валидным JSON. Без пояснений, без markdown.",
                max_tokens=800,
            )
            import json, re
            json_match = re.search(r'\{.*\}', analysis, re.DOTALL)
            if json_match:
                plan_data = json.loads(json_match.group())
                days = plan_data.get("days", 7)
                posts = plan_data.get("posts", [])

                posts_text = "\n".join([
                    f"День {p['day']}: {p['title']} [{p.get('format', '')}]"
                    for p in posts
                ])

                # Сохраняем структуру
                import hashlib
                plan_key = hashlib.md5(f"{topic}:{days}".encode()).hexdigest()[:8]
                await db.set_setting(f"plan_{plan_key}", json.dumps({"topic": topic, "days": days}))

                await message.answer(
                    f"📋 <b>Предлагаю структуру на {days} постов:</b>\n\n{posts_text}",
                    reply_markup=InlineKeyboardBuilder()
                    .button(text=f"✅ Создать {days} постов", callback_data=f"cpp:{plan_key}")
                    .button(text="✏️ Указать кол-во вручную", callback_data="plan_manual")
                    .button(text="❌ Отмена", callback_data="back_menu")
                    .adjust(1)
                    .as_markup(),
                    parse_mode="HTML"
                )
                await state.clear()
                return
        except Exception as e:
            logger.error(f"ai_plan_handler: ошибка анализа темы: {e}")
            # Fallback — используем 7 дней
            days = 7

        await message.answer(f"⏳ <b>Составляю контент-план на {days} дней...</b>", parse_mode="HTML")

    user_prompt = (
        f"Составь контент-план на {days} дней для Telegram-канала GEORIS.\n"
        f"Тема: «{topic}»\n"
        f"Аудитория: владельцы квартир в Москве, которые думают о перепланировке или уже начали её."
    )

    plan = None
    error_message = None
    try:
        plan = await router_ai.generate_response(
            user_prompt=user_prompt,
            system_prompt=_PLAN_SYSTEM,
            max_tokens=2000,  # Увеличено до 2000
        )
    except Exception as e:
        error_message = str(e)
        logger.error("ai_plan_handler: router_ai error: %s", e)
        # Отправляем ошибку в топик "Логи"
        try:
            bot = Bot(token=BOT_TOKEN)
            await bot.send_message(
                LEADS_GROUP_CHAT_ID,
                f"⚠️ <b>Ошибка нейросети</b>\n\n"
                f"Тема: <code>{topic[:100]}</code>\n"
                f"Ошибка: <code>{error_message[:500]}</code>",
                message_thread_id=THREAD_ID_LOGS,
                parse_mode="HTML",
            )
            await bot.session.close()
        except Exception as notify_err:
            logger.error("Не удалось отправить ошибку в топик: %s", notify_err)
    
    if not plan:
        await message.answer(
            f"⚠️ <b>Ошибка генерации</b>\n\n"
            f"{f'Ошибка: {error_message[:200]}' if error_message else 'Попробуйте ещё раз.'}",
            reply_markup=get_back_btn(),
            parse_mode="HTML",
        )
        await state.clear()
        return

    await message.bot.send_message(
        chat_id=LEADS_GROUP_CHAT_ID,
        message_thread_id=THREAD_ID_CONTENT_PLAN,
        text=f"📋 <b>Контент-план: {topic}</b> ({days} дней)\n\n{plan}",
        parse_mode="HTML"
    )

    # Сохраняем тему в БД чтобы не передавать в callback_data (лимит 64 байта)
    import hashlib, json
    plan_key = hashlib.md5(f"{topic}:{days}".encode()).hexdigest()[:8]
    await db.set_setting(f"plan_{plan_key}", json.dumps({"topic": topic, "days": days, "posts": []}))

    await message.answer(
        f"✅ <b>Контент-план на {days} дней готов!</b>\n"
        f"Отправил в топик «Контент-план».\n\n"
        f"<b>Создать посты с обложками для каждого дня?</b>",
        reply_markup=InlineKeyboardBuilder()
        .button(text="📝 Создать посты", callback_data=f"cpp:{plan_key}")
        .button(text="❌ Нет", callback_data="back_menu")
        .as_markup(),
        parse_mode="HTML"
    )
    await state.clear()


@content_router.callback_query(F.data.startswith("plan_manual"))
async def plan_manual_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "Укажите количество дней и тему через запятую:\n<code>7, перепланировка</code>",
        parse_mode="HTML", reply_markup=get_back_btn()
    )
    await state.set_state(ContentStates.ai_plan)


@content_router.callback_query(F.data.startswith("plan_manual"))
async def plan_manual_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "Укажите количество дней и тему через запятую:\n<code>7, перепланировка</code>",
        parse_mode="HTML", reply_markup=get_back_btn()
    )
    await state.set_state(ContentStates.ai_plan)


@content_router.callback_query(F.data.startswith("cpp:"))
async def create_plan_posts(callback: CallbackQuery, state: FSMContext):
    """Создаёт черновики постов для каждого дня плана: текст + обложка -> БД -> топик 85."""
    logger.warning(f"DEBUG cpp: handler reached! data={callback.data}")
    import json
    plan_key = callback.data.split(":", 1)[1]
    plan_data = await db.get_setting(f"plan_{plan_key}")
    if not plan_data:
        await callback.answer("❌ План не найден, создайте заново")
        return
    plan_info = json.loads(plan_data)
    topic = plan_info["topic"]
    days = plan_info["days"]
    plan_posts = plan_info.get("posts", [])

    created_ids = []

    await callback.answer("Создаю посты...")
    await callback.message.edit_text(
        f"<b>Создаю {days} черновиков...</b>\n\nДля каждого дня: текст + обложка -&gt; сохраняю в базу -&gt; топик Черновики",
        parse_mode="HTML"
    )

    created = 0
    errors = 0

    for i in range(1, days + 1):
        try:
            await callback.message.edit_text(
                f"<b>День {i}/{days}...</b>\n\nСоздано: {created} | Ошибок: {errors}",
                parse_mode="HTML"
            )
        except Exception:
            pass

        # 1. Генерируем текст поста
        _formats = ["экспертный совет", "кейс клиента", "лайфхак", "вопрос аудитории", "интересный факт", "разбор ошибок", "пошаговая инструкция"]
        post_format = _formats[(i - 1) % len(_formats)]
        # Берём описание дня из плана если есть
        day_info = next((p for p in plan_posts if p.get("day") == i), None)
        day_title = day_info.get("title", "") if day_info else ""
        day_idea = day_info.get("idea", "") if day_info else ""
        day_format = day_info.get("format", post_format) if day_info else post_format
        post_prompt = (
            f"Напиши готовый пост для Telegram-канала компании GEORIS (перепланировка квартир в Москве).\n"
            f"Тема: {topic}. День {i} из {days}.\n"
            + (f"Заголовок поста: {day_title}\n" if day_title else "")
            + (f"Идея: {day_idea}\n" if day_idea else "")
            + f"Формат: {day_format}.\n\n"
            "ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ:\n"
            "1. Объём: 200-250 слов, текст полный и законченный\n"
            "2. Начни с цепляющего первого предложения\n"
            f"3. Раскрой тему через формат '{day_format}' — включая все детали из идеи\n"
            "4. В конце ОБЯЗАТЕЛЬНО: призыв записаться на консультацию в GEORIS. НЕ вставляй ссылки — только текст\n"
            "5. Тон: экспертный, дружелюбный, живой\n"
            "6. Эмодзи — 3-5 штук по смыслу\n"
            "7. НЕ пиши заголовок отдельно — начинай сразу с текста поста"
        )
        post_text = None
        try:
            post_text = await router_ai.generate_response(
                user_prompt=post_prompt,
                system_prompt=_PLAN_SYSTEM,
                max_tokens=600,
            )
        except Exception as e:
            logger.error(f"create_plan_posts: ошибка текста день {i}: {e}")

        if not post_text:
            errors += 1
            continue

        # 2. Генерируем обложку на основе текста поста
        post_excerpt = post_text[:150].replace('"', '').replace("'", '').strip()
        art_prompt = (
            f"{post_excerpt}. "
            "Moscow apartment interior, professional architectural visualization, "
            "modern realistic render, bright natural light. "
            "No text, no words, no letters, no watermarks - image only."
        )
        image_b64 = await _auto_generate_image(art_prompt)
        image_file_id = None

        if image_b64:
            try:
                image_bytes = base64.b64decode(image_b64)
                photo = BufferedInputFile(image_bytes, filename=f"plan_day_{i}.jpg")
                sent = await callback.bot.send_photo(
                    chat_id=LEADS_GROUP_CHAT_ID,
                    message_thread_id=THREAD_ID_DRAFTS,
                    photo=photo,
                    caption=f"Обложка день {i}: {topic}",
                )
                image_file_id = sent.photo[-1].file_id
            except Exception as e:
                logger.error(f"create_plan_posts: ошибка обложки день {i}: {e}")

        # 3. Применяем квиз и хэштеги, сохраняем черновик в БД
        post_text_full = ensure_quiz_and_hashtags(post_text)
        try:
            post_id = await db.add_content_post(
                title=f"День {i}: {topic}",
                body=post_text_full,
                cta="",
                channel="draft",
                status="draft",
                image_url=image_file_id,
                theme=topic,
            )
            created += 1
            created_ids.append(post_id)
        except Exception as e:
            logger.error(f"create_plan_posts: ошибка БД день {i}: {e}")
            errors += 1
            continue

        # 4. Анонс черновика в топик 85
        try:
            kb = InlineKeyboardBuilder()
            kb.button(text="📤 Во все каналы", callback_data=f"pub_all:{post_id}")
            kb.button(text="⏰ Запланировать", callback_data=f"schedule:{post_id}")
            kb.button(text="📤 TG", callback_data=f"pub_tg:{post_id}")
            kb.button(text="📘 VK", callback_data=f"pub_vk:{post_id}")
            kb.button(text="✏️ Редактировать", callback_data=f"edit_draft:{post_id}")
            kb.adjust(2)
            draft_preview = post_text_full[:800] + ("..." if len(post_text_full) > 800 else "")
            await callback.bot.send_message(
                chat_id=LEADS_GROUP_CHAT_ID,
                message_thread_id=THREAD_ID_DRAFTS,
                text=f"<b>День {i}/{days}</b> — {topic}\n\n{draft_preview}",
                reply_markup=kb.as_markup(),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"create_plan_posts: ошибка топика день {i}: {e}")

    # Сохраняем список post_id серии для массового планирования
    import json
    series_ids = ",".join(str(pid) for pid in created_ids)
    series_key = f"series_ids_{plan_key}"
    await db.set_setting(series_key, series_ids)

    kb_final = InlineKeyboardBuilder()
    kb_final.button(text="📅 Запланировать всю серию", callback_data=f"schedule_series:{plan_key}")
    kb_final.button(text="✅ Готово", callback_data="back_menu")
    kb_final.adjust(1)

    await callback.message.edit_text(
        ("✅" if errors == 0 else "⚠️") + f" <b>Готово!</b>\n\nСоздано черновиков: <b>{created}/{days}</b>\nОшибок: <b>{errors}</b>\n\nЧерновики с кнопками публикации — в топике Черновики",
        reply_markup=kb_final.as_markup(),
        parse_mode="HTML",
    )




@content_router.callback_query(F.data.startswith("edit_draft:"))
async def edit_draft_start(callback: CallbackQuery, state: FSMContext):
    """Начало редактирования черновика."""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    if not post:
        await callback.answer("❌ Пост не найден")
        return
    await state.update_data(edit_post_id=post_id)
    await state.set_state(ContentStates.edit_draft)
    await callback.message.answer(
        f"✏️ <b>Редактирование черновика #{post_id}</b>\n\n"
        f"Текущий текст:\n<blockquote>{post['body'][:500]}...</blockquote>\n\n"
        f"Напишите новый текст поста (или /skip чтобы оставить текущий):",
        parse_mode="HTML",
        reply_markup=get_back_btn()
    )
    await callback.answer()


@content_router.message(ContentStates.edit_draft)
async def edit_draft_save(message: Message, state: FSMContext):
    """Сохраняет отредактированный текст черновика."""
    data = await state.get_data()
    post_id = data.get("edit_post_id")

    if message.text == "/skip":
        await state.clear()
        await message.answer("✅ Текст оставлен без изменений.", reply_markup=get_back_btn())
        return

    new_text = ensure_quiz_and_hashtags(message.text)
    try:
        await db.update_content_plan_entry(post_id, body=new_text)
        await state.clear()
        post = await db.get_content_post(post_id)
        kb = InlineKeyboardBuilder()
        kb.button(text="📤 Во все каналы", callback_data=f"pub_all:{post_id}")
        kb.button(text="⏰ Запланировать", callback_data=f"schedule:{post_id}")
        kb.button(text="📤 TG", callback_data=f"pub_tg:{post_id}")
        kb.button(text="📘 VK", callback_data=f"pub_vk:{post_id}")
        kb.button(text="✏️ Редактировать", callback_data=f"edit_draft:{post_id}")
        kb.adjust(2)
        await message.answer(
            f"✅ <b>Черновик #{post_id} обновлён!</b>\n\n{new_text[:600]}...",
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"edit_draft_save: ошибка: {e}")
        await message.answer(f"❌ Ошибка сохранения: {e}", reply_markup=get_back_btn())

@content_router.callback_query(F.data.startswith("schedule_series:"))
async def schedule_series_start(callback: CallbackQuery, state: FSMContext):
    """Массовое планирование серии постов"""
    plan_key = callback.data.split(":", 1)[1]
    await state.update_data(schedule_plan_key=plan_key)
    await state.set_state(ContentStates.schedule_series)
    
    from datetime import datetime, timedelta
    now = datetime.now()
    tomorrow = (now + timedelta(days=1)).strftime("%d.%m")
    
    await callback.message.answer(
        "📅 <b>Запланировать всю серию</b>\n\n"
        "Введите дату первой публикации и время:\n"
        "<code>ДД.ММ ЧЧ:ММ</code>\n\n"
        f"Например: <code>{tomorrow} 10:00</code>\n\n"
        "<i>Каждый следующий пост — через 24 часа</i>",
        parse_mode="HTML",
        reply_markup=get_back_btn()
    )
    await callback.answer()

@content_router.message(ContentStates.schedule_series)
async def schedule_series_input(message: Message, state: FSMContext):
    """Получаем дату и планируем все посты серии"""
    data = await state.get_data()
    plan_key = data.get("schedule_plan_key")
    
    try:
        from datetime import datetime, timedelta
        dt = datetime.strptime(message.text.strip(), "%d.%m %H:%M").replace(year=datetime.now().year)
    except ValueError:
        await message.answer("❌ Неверный формат. Пример: <code>25.03 10:00</code>", parse_mode="HTML")
        return
    
    # Получаем список post_id серии
    series_ids_str = await db.get_setting(f"series_ids_{plan_key}")
    if not series_ids_str:
        await message.answer("❌ Серия не найдена", reply_markup=get_back_btn())
        await state.clear()
        return
    
    post_ids = [int(pid) for pid in series_ids_str.split(",") if pid]
    
    scheduled = []
    for i, post_id in enumerate(post_ids):
        publish_dt = dt + timedelta(days=i)
        await db.update_content_plan_entry(post_id, status="approved", publish_date=publish_dt)
        scheduled.append(f"День {i+1}: {publish_dt.strftime('%d.%m в %H:%M')}")
    
    result = "\n".join(scheduled)
    await message.answer(
        f"✅ <b>Серия запланирована!</b>\n\n{result}\n\n"
        f"Посты будут опубликованы автоматически во все каналы.",
        parse_mode="HTML",
        reply_markup=get_back_btn()
    )
    await state.clear()

# === 📰 НОВОСТЬ ===

# Категории новостей по нашей специфике
_NEWS_CATEGORIES = {
    "renovation": ("🔨 Перепланировка и согласование", "изменения в законодательстве о перепланировках, новые требования МЖИ, упрощение или ужесточение согласования"),
    "construction": ("🏗 Строительство и материалы", "новые строительные технологии, современные материалы, тенденции в строительстве жилья в Москве"),
    "mortgage": ("🏦 Ипотека и финансы", "ставки по ипотеке, государственные программы, решения ЦБ, льготная ипотека для москвичей"),
    "realty": ("🏠 Недвижимость и рынок", "цены на квартиры в Москве, тренды рынка недвижимости, новостройки и вторичное жильё"),
    "renovation_design": ("🎨 Дизайн и ремонт", "тренды в дизайне интерьеров, новые решения для небольших квартир, умный дом"),
    "custom": ("✏️ Своя тема", ""),
}

_NEWS_SYSTEM = (
    "Ты — контент-редактор компании GEORIS, специализирующейся на перепланировках квартир в Москве.\n"
    "Пиши экспертный информационный пост на заданную тему. Требования:\n"
    "— Структура: яркий заголовок → суть → что это значит для москвичей → лёгкий призыв к действию\n"
    "— Объём: 150-200 слов\n"
    "— Тон: уверенный, информативный, без официоза\n"
    "— Эмодзи — умеренно, по смыслу\n"
    "— Технические термины (МЖИ, СНиП, трассировка) — ТОЛЬКО если они органично вписываются в тему\n"
    "— ЗАПРЕЩЕНО: выдумывать конкретные даты, номера законов, имена чиновников\n"
    "— Если тема не связана с нашей сферой — вежливо уйди на смежную тему (недвижимость, жильё, ремонт)\n"
    "— НЕ добавляй хештеги и ссылки — они добавятся автоматически"
)


async def _generate_news_by_topic(message_or_callback, state: FSMContext, topic: str, hint: str = "", is_callback: bool = False):
    """Генерация новостного поста по теме."""
    if is_callback:
        await message_or_callback.message.edit_text("🔍 <b>Пишу новость...</b>", parse_mode="HTML")
        target = message_or_callback.message
    else:
        await message_or_callback.answer("🔍 <b>Пишу новость...</b>", parse_mode="HTML")
        target = message_or_callback

    user_prompt = f"Напиши информационный пост для Telegram-канала GEORIS на тему: «{topic}»."
    if hint:
        user_prompt += f"\nАкцент: {hint}"

    news = None
    error_message = None
    try:
        news = await router_ai.generate_response(
            user_prompt=user_prompt,
            system_prompt=_NEWS_SYSTEM,
            max_tokens=2000,  # Увеличено до 2000
        )
    except Exception as e:
        error_message = str(e)
        logger.error("news_handler: router_ai error: %s", e)
        # Отправляем ошибку в топик "Логи"
        try:
            bot = Bot(token=BOT_TOKEN)
            await bot.send_message(
                LEADS_GROUP_CHAT_ID,
                f"⚠️ <b>Ошибка нейросети</b>\n\n"
                f"Тема новости: <code>{topic[:100]}</code>\n"
                f"Ошибка: <code>{error_message[:500]}</code>",
                message_thread_id=THREAD_ID_LOGS,
                parse_mode="HTML",
            )
            await bot.session.close()
        except Exception as notify_err:
            logger.error("Не удалось отправить ошибку в топик: %s", notify_err)
    
    if not news:
        err_msg = f"⚠️ <b>Не удалось сгенерировать новость</b>\n\n{f'Ошибка: {error_message[:200]}' if error_message else 'Попробуйте другую тему.'}"
        if is_callback:
            await message_or_callback.message.edit_text(err_msg, reply_markup=get_back_btn(), parse_mode="HTML")
        else:
            await message_or_callback.answer(err_msg, reply_markup=get_back_btn())
        await state.clear()
        return

    post_id = await show_preview(target, news)
    await state.set_state(ContentStates.preview_mode)
    await state.update_data(post_id=post_id, text=news)


async def news_start(message: Message, state: FSMContext):
    builder = InlineKeyboardBuilder()
    for key, (label, _) in _NEWS_CATEGORIES.items():
        builder.button(text=label, callback_data=f"topic_news:{key}")
    builder.adjust(1)
    await message.answer(
        "📰 <b>Экспертная новость</b>\n\n"
        "Выберите тему — напишем актуальный пост по нашей специфике:\n"
        "<i>Нет подходящего? Выберите «Своя тема»</i>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.ai_news_choose)


@content_router.callback_query(F.data.startswith("topic_news:"), ContentStates.ai_news_choose)
async def news_topic_selected(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]
    if key == "custom":
        await callback.answer()
        await callback.message.edit_text(
            "📰 Введите тему новости:\n\n"
            "Например: <i>новые правила перепланировки, льготная ипотека, тренды ремонта 2025</i>",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
        await state.set_state(ContentStates.ai_news)
        return

    category = _NEWS_CATEGORIES.get(key)
    if not category:
        await callback.answer("Неизвестная категория")
        return

    label, hint = category
    await callback.answer()
    await _generate_news_by_topic(callback, state, label.split(" ", 1)[-1], hint=hint, is_callback=True)


@content_router.message(ContentStates.ai_news)
async def ai_news_handler(message: Message, state: FSMContext):
    topic = (message.text or "").strip()
    if not topic:
        await message.answer("Введите тему текстом.")
        return
    await _generate_news_by_topic(message, state, topic, is_callback=False)


# === 🎉 ПРАЗДНИК РФ ===

# Официальные праздники РФ для поста в канал
HOLIDAYS_RF = [
    ("Новый год", "Новый год"),
    ("23 февраля", "23 февраля, День защитника Отечества"),
    ("8 Марта", "8 Марта, Международный женский день"),
    ("1 Мая", "1 Мая, Праздник весны и труда"),
    ("9 Мая", "9 Мая, День Победы"),
    ("12 июня", "12 июня, День России"),
    ("День строителя", "День строителя (второе воскресенье августа)"),
    ("День народного единства", "4 ноября, День народного единства"),
]

async def holiday_rf_start(message: Message, state: FSMContext):
    builder = InlineKeyboardBuilder()
    for label, _ in HOLIDAYS_RF:
        builder.button(text=label, callback_data=f"holiday_rf:{label}")
    builder.adjust(2)
    await message.answer(
        "🎉 <b>Поздравление с официальным праздником РФ</b>\n\nВыберите праздник:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.holiday_rf)


_HOLIDAY_SYSTEM = (
    "Ты — голос бренда GEORIS (перепланировки квартир в Москве).\n"
    "Напиши тёплое праздничное поздравление для Telegram-канала. Требования:\n"
    "— Начни с яркого поздравления, создай праздничное настроение\n"
    "— Свяжи праздник с темой дома, уюта, семьи или пространства — органично, без натяжки\n"
    "— Лёгкий юмор или трогательный момент — приветствуется\n"
    "— Объём: 80-120 слов\n"
    "— Эмодзи: уместно и щедро\n"
    "— Тон: тёплый, человечный, не корпоративный\n"
    "— ЗАПРЕЩЕНО: технические термины (МЖИ, СНиП), прямые продажи, шаблонные фразы «команда компании поздравляет»\n"
    "— НЕ добавляй хештеги и ссылки — они добавятся автоматически"
)


@content_router.callback_query(F.data.startswith("holiday_rf:"), ContentStates.holiday_rf)
async def holiday_rf_selected(callback: CallbackQuery, state: FSMContext):
    label = callback.data.split(":", 1)[1]
    occasion = next((occ for btn_label, occ in HOLIDAYS_RF if btn_label == label), label)
    await callback.answer()
    await callback.message.edit_text(f"⏳ <b>Пишу поздравление с {label}...</b>", parse_mode="HTML")
    try:
        user_prompt = (
            f"Напиши поздравление с праздником «{occasion}» для подписчиков Telegram-канала GEORIS."
        )
        body = None
        error_message = None
        try:
            body = await router_ai.generate_response(
                user_prompt=user_prompt,
                system_prompt=_HOLIDAY_SYSTEM,
                max_tokens=2000,  # Увеличено до 2000
            )
        except Exception as e:
            error_message = str(e)
            logger.error("holiday_handler: router_ai error: %s", e)
            # Отправляем ошибку в топик "Логи"
            try:
                bot = Bot(token=BOT_TOKEN)
                await bot.send_message(
                    LEADS_GROUP_CHAT_ID,
                    f"⚠️ <b>Ошибка нейросети</b>\n\n"
                    f"Праздник: <code>{label}</code>\n"
                    f"Ошибка: <code>{error_message[:500]}</code>",
                    message_thread_id=THREAD_ID_LOGS,
                    parse_mode="HTML",
                )
                await bot.session.close()
            except Exception as notify_err:
                logger.error("Не удалось отправить ошибку в топик: %s", notify_err)
        
        if not body or not body.strip():
            body = f"🎉 С праздником — {label}!\n\nПусть ваш дом всегда будет местом, где хочется возвращаться. Уюта, тепла и вдохновения!"
        post_id = await db.add_content_post(
            title=f"Праздник: {label}",
            body=body,
            cta="",
            channel="holiday",
            status="preview"
        )
        post_id = await show_preview(callback.message, body, post_id=post_id)
        await state.set_state(ContentStates.preview_mode)
        await state.update_data(post_id=post_id, text=body)
    except Exception as e:
        logger.exception("holiday_rf")
        await callback.message.edit_text(f"❌ Ошибка: {e}", reply_markup=get_back_btn())
        await state.clear()


# === 📝 БЫСТРЫЙ ТЕКСТ ===

async def quick_start(message: Message, state: FSMContext):
    await state.update_data(quick_prompt_prefix=None, fact_from_lead=None)
    await message.answer(
        "📝 <b>Быстрый текст</b>\n\n"
        "Введите тему:",
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.ai_text)


# === 💡 ИНТЕРЕСНЫЙ ФАКТ ===
# Развлекательный формат: короткий, живой, без инструкций.
# Читатель узнаёт что-то неожиданное — и запоминает канал.

_FACT_CATEGORIES = {
    "realty": {
        "label": "🏠 Квартиры и Москва",
        "hint": "Необычный факт о московских квартирах, планировках, новостройках или истории жилья.",
    },
    "numbers": {
        "label": "🔢 Цифры и рекорды",
        "hint": "Удивительная статистика или рекорд из мира стройки, ремонта или недвижимости.",
    },
    "history": {
        "label": "📜 История жилья",
        "hint": "Интересный исторический факт о хрущёвках, сталинках, советских нормах или "
                "законах о перепланировке в СССР и России.",
    },
    "funny": {
        "label": "😄 Курьёз из жизни",
        "hint": "Смешной или неожиданный случай из практики ремонта или согласования. "
                "Реальные ситуации, без выдумки.",
    },
    "custom": {
        "label": "✏️ Своя тема",
        "hint": None,
    },
}

_FACT_SYSTEM = (
    "Ты — автор яркого Telegram-канала о недвижимости и жизни в Москве.\n\n"
    "Пишешь короткие, живые посты, которые читают до конца.\n\n"
    "ПРАВИЛА:\n"
    "• 60-90 слов максимум\n"
    "• Начни с неожиданного факта, вопроса или цифры — сразу цепляй\n"
    "• Лёгкий, разговорный тон — без канцелярита и инструкций\n"
    "• Эмодзи уместно, не перегружай\n"
    "• Если тема близка к ремонту — в конце одно предложение-намёк на GEORIS (без навязывания)\n\n"
    "СТРОГО ЗАПРЕЩЕНО:\n"
    "• Писать процедуры, требования, шаги согласования\n"
    "• Принудительно вставлять: МЖИ, СНиП, трассировка, акты скрытых работ — только если сами по себе делают факт интереснее\n"
    "• Длинные абзацы\n"
    "• Явные продажи и навязчивые CTA\n"
    "• Повторные хештеги — не добавляй их, они будут добавлены автоматически"
)


async def _generate_fact(topic_hint: str) -> str:
    """Генерирует интересный факт по подсказке темы."""
    prompt = (
        f"Напиши интересный факт на тему: «{topic_hint}».\n\n"
        f"Формат: один короткий пост для Telegram, 60-90 слов."
    )
    try:
        return await router_ai.generate_response(
            user_prompt=prompt,
            system_prompt=_FACT_SYSTEM,
            max_tokens=2000,  # Увеличено до 2000
        ) or ""
    except Exception as e:
        logger.error("generate_fact: router_ai error: %s", e)
        # Отправляем ошибку в топик "Логи"
        try:
            bot = Bot(token=BOT_TOKEN)
            await bot.send_message(
                LEADS_GROUP_CHAT_ID,
                f"⚠️ <b>Ошибка нейросети</b>\n\n"
                f"Тема факта: <code>{topic_hint[:100]}</code>\n"
                f"Ошибка: <code>{str(e)[:500]}</code>",
                message_thread_id=THREAD_ID_LOGS,
                parse_mode="HTML",
            )
            await bot.session.close()
        except Exception as notify_err:
            logger.error("Не удалось отправить ошибку в топик: %s", notify_err)
        return ""


async def fact_start(message: Message, state: FSMContext):
    """Показывает выбор категории интересного факта."""
    await state.clear()
    builder = InlineKeyboardBuilder()
    for key, cat in _FACT_CATEGORIES.items():
        builder.button(text=cat["label"], callback_data=f"fact_cat:{key}")
    builder.adjust(1)
    await message.answer(
        "💡 <b>Интересный факт</b>\n\n"
        "Выберите категорию — бот напишет яркий короткий пост с картинкой.\n\n"
        "<i>Развлекательный контент оживляет ленту и удерживает подписчиков.</i>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.ai_fact_choose)


@content_router.callback_query(F.data.startswith("fact_cat:"), ContentStates.ai_fact_choose)
async def fact_category_selected(callback: CallbackQuery, state: FSMContext):
    key = callback.data.split(":", 1)[1]

    if key == "custom":
        await callback.answer()
        await callback.message.edit_text(
            "💡 <b>Своя тема</b>\n\nВведите тему интересного факта:",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
        await state.update_data(quick_prompt_prefix="fact")
        await state.set_state(ContentStates.ai_text)
        return

    cat = _FACT_CATEGORIES.get(key)
    if not cat:
        await callback.answer("Неизвестная категория")
        return

    await callback.answer()
    await callback.message.edit_text(
        f"⏳ <b>Пишу интересный факт...</b>\n<i>{cat['label']}</i>",
        parse_mode="HTML"
    )

    text = await _generate_fact(cat["hint"])
    if not text:
        await callback.message.edit_text("❌ Ошибка генерации. Попробуйте ещё раз.", reply_markup=get_back_btn())
        await state.clear()
        return

    post_id = await show_preview(callback.message, text)
    await state.set_state(ContentStates.preview_mode)
    await state.update_data(post_id=post_id)


@content_router.message(ContentStates.ai_text)
async def ai_text_handler(message: Message, state: FSMContext):
    topic = message.text
    data = await state.get_data()
    is_fact = data.get("quick_prompt_prefix") == "fact"
    await message.answer("⏳ <b>Пишу...</b>" if not is_fact else "⏳ <b>Пишу интересный факт...</b>", parse_mode="HTML")

    if is_fact:
        # Своя тема для интересного факта — живой и короткий формат без навязанного жаргона
        prompt = f"Напиши интересный факт на тему: «{topic}».\n\nФормат: один короткий пост для Telegram, 60-90 слов."
        text = None
        error_message = None
        try:
            text = await router_ai.generate_response(
                user_prompt=prompt,
                system_prompt=_FACT_SYSTEM,
                max_tokens=2000,  # Увеличено до 2000
            )
        except Exception as e:
            error_message = str(e)
            logger.error("quick_text_handler (fact): router_ai error: %s", e)
            # Отправляем ошибку в топик "Логи"
            try:
                bot = Bot(token=BOT_TOKEN)
                await bot.send_message(
                    LEADS_GROUP_CHAT_ID,
                    f"⚠️ <b>Ошибка нейросети</b>\n\n"
                    f"Тема факта: <code>{topic[:100]}</code>\n"
                    f"Ошибка: <code>{error_message[:500]}</code>",
                    message_thread_id=THREAD_ID_LOGS,
                    parse_mode="HTML",
                )
                await bot.session.close()
            except Exception as notify_err:
                logger.error("Не удалось отправить ошибку в топик: %s", notify_err)
        
        if not text:
            # Даже при ошибке показываем кнопки публикации с fallback текстом
            fallback_text = (
                f"<b>🏠 Перепланировка по теме: {topic}</b>\n\n"
                f"Каждый объект уникален. Правильный подход — согласование с МЖИ, "
                f"расчёт несущих конструкций и трассировка изменений по СНиП.\n\n"
                f"👉 Записаться на консультацию: @Parkhovenko_i_kompaniya_bot"
            )
            post_id = await db.add_content_post(
                title=f"Факт: {topic[:40]}",
                body=fallback_text,
                cta="",
                channel="preview",
                status="preview"
            )
            await show_preview(message, fallback_text, post_id=post_id)
            await state.set_state(ContentStates.preview_mode)
            await state.update_data(post_id=post_id)
            return
        
        post_id = await show_preview(message, text)
        await state.set_state(ContentStates.preview_mode)
        await state.update_data(post_id=post_id)
        return
    else:
        prompt = (
            f"Пост для TG на тему «{topic}». "
            f"Экспертный, живой стиль. 100-150 слов. "
            f"Эмодзи + призыв к консультации @georis_bot"
        )
    
    text = None
    error_message = None
    try:
        text = await router_ai.generate_response(
            user_prompt=prompt,
            max_tokens=2000,  # Увеличено до 2000
        )
    except Exception as e:
        error_message = str(e)
        logger.error("quick_text_handler: router_ai error: %s", e)
        # Отправляем ошибку в топик "Логи"
        try:
            bot = Bot(token=BOT_TOKEN)
            await bot.send_message(
                LEADS_GROUP_CHAT_ID,
                f"⚠️ <b>Ошибка нейросети</b>\n\n"
                f"Тема: <code>{topic[:100]}</code>\n"
                f"Ошибка: <code>{error_message[:500]}</code>",
                message_thread_id=THREAD_ID_LOGS,
                parse_mode="HTML",
            )
            await bot.session.close()
        except Exception as notify_err:
            logger.error("Не удалось отправить ошибку в топик: %s", notify_err)

    if not text:
        # Даже при ошибке показываем кнопки публикации с fallback текстом
        fallback_text = (
            f"<b>🏠 Перепланировка по теме: {topic}</b>\n\n"
            f"Каждый объект уникален. Правильный подход — согласование с МЖИ, "
            f"расчёт несущих конструкций и трассировка изменений по СНиП.\n\n"
            f"👉 Записаться на консультацию: @Parkhovenko_i_kompaniya_bot"
        )
        post_id = await db.add_content_post(
            title=f"Быстрый текст: {topic[:40]}",
            body=fallback_text,
            cta="",
            channel="preview",
            status="preview"
        )
        await show_preview(message, fallback_text, post_id=post_id)
        await state.set_state(ContentStates.preview_mode)
        await state.update_data(post_id=post_id, text=fallback_text)
        return

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
    """Отправка поста в канал через централизованный Publisher."""
    # ── ЦЕНТРАЛИЗАЦИЯ: Используем единый сервис Publisher ───────────────────────────
    from services.publisher import publisher
    
    # Устанавливаем bot в publisher, если еще не установлен
    if not publisher.bot:
        publisher.bot = bot
    
    text = ensure_quiz_and_hashtags(post['body'])
    
    try:
        image_bytes = None
        if post.get("image_url"):
            image_bytes = await download_photo(bot, post["image_url"])
        
        # Используем Publisher для публикации
        success = await publisher.publish_to_telegram(channel_id, text, image_bytes)
        
        if success:
            # Формируем ссылку на пост (Publisher не возвращает message_id, используем приблизительную)
            if str(channel_id).startswith("-100"):
                # Для приватных каналов ссылка будет примерной
                link = f"https://t.me/c/{str(channel_id).replace('-100', '')}/1"
            else:
                link = f"https://t.me/{channel_id}/1"
            return True, link
        else:
            return False, "Ошибка публикации через Publisher"
    except Exception as e:
        logger.error(f"Ошибка в send_post: {e}")
        return False, str(e)


async def _check_daily_limit(callback) -> bool:
    """
    Проверяет лимит публикаций на сегодня (POSTS_PER_DAY_LIMIT из config).
    Если лимит исчерпан — уведомляет пользователя и возвращает False.
    """
    from config import POSTS_PER_DAY_LIMIT
    if POSTS_PER_DAY_LIMIT <= 0:
        return True  # лимит отключён
    try:
        count = await db.count_published_today()
    except Exception:
        return True  # не удалось проверить — пропускаем
    if count >= POSTS_PER_DAY_LIMIT:
        await callback.answer(
            f"⛔ Лимит на сегодня: {POSTS_PER_DAY_LIMIT} поста опубликовано. "
            f"Следующую публикацию можно сделать завтра.",
            show_alert=True,
        )
        return False
    return True


@content_router.callback_query(F.data.startswith("pub_georis:"))
async def publish_georis(callback: CallbackQuery, state: FSMContext):
    """Публикация только в GEORIS"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)

    if not post:
        await callback.answer("❌ Пост не найден")
        return
    if not await _check_daily_limit(callback):
        return

    await callback.answer("🚀 Публикую в GEORIS...")
    
    success, result = await send_post(callback.bot, CHANNEL_ID_GEORIS, post, "GEORIS")
    
    if success:
        await db.update_content_post(post_id, status="published")
        await callback.message.edit_text(
            f"✅ <b>Опубликовано в GEORIS</b>\n\n🔗 <a href='{result}'>Ссылка на пост</a>",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            f"❌ <b>Ошибка публикации в GEORIS</b>\n\n{result}",
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
    if not await _check_daily_limit(callback):
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


@content_router.callback_query(F.data.startswith("pub_max:"))
async def publish_max(callback: CallbackQuery, state: FSMContext):
    """Публикация в канал MAX.ru"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)

    if not post:
        await callback.answer("❌ Пост не найден")
        return

    await callback.answer("📱 Публикую в MAX...")

    try:
        agent = ContentAgent()
        ok = await agent.post_to_max(post_id)
        if ok:
            await db.update_content_post(post_id, status="published")
            await callback.message.edit_text(
                "✅ <b>Опубликовано в MAX</b>\n\nПост отправлен в ваш канал на MAX.ru.",
                reply_markup=get_back_btn(),
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                "❌ <b>Ошибка публикации в MAX</b>\n\nПроверьте MAX_DEVICE_TOKEN в .env и что канал создан в приложении MAX.",
                reply_markup=get_back_btn(),
                parse_mode="HTML"
            )
    except Exception as e:
        logger.exception("pub_max error")
        await callback.message.edit_text(
            f"❌ <b>Ошибка публикации в MAX</b>\n\n{str(e)}",
            reply_markup=get_back_btn(),
            parse_mode="HTML"
        )

    await state.clear()


@content_router.callback_query(F.data.startswith("pub_all:"))
async def publish_all(callback: CallbackQuery, state: FSMContext):
    """Централизованная публикация через Publisher во все каналы."""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)

    if not post:
        await callback.answer("❌ Пост не найден")
        return
    if not await _check_daily_limit(callback):
        return

    await callback.answer("🚀 Публикую...")
    
    # ── ЦЕНТРАЛИЗАЦИЯ: Используем единый сервис Publisher ───────────────────────────
    from services.publisher import publisher
    
    # Устанавливаем bot в publisher
    if not publisher.bot:
        publisher.bot = callback.bot
    
    text = ensure_quiz_and_hashtags(post['body'])
    results = []
    
    # Подготавливаем изображение
    image_bytes = None
    if post.get("image_url"):
        image_bytes = await download_photo(callback.bot, post["image_url"])
    
    # TG GEORIS через Publisher
    try:
        success = await publisher.publish_to_telegram(CHANNEL_ID_GEORIS, text, image_bytes)
        results.append("✅ GEORIS TG" if success else "❌ GEORIS TG")
    except Exception as e:
        results.append(f"❌ GEORIS: {e}")
    
    # TG ДОМ ГРАНД через Publisher
    try:
        success = await publisher.publish_to_telegram(CHANNEL_ID_DOM_GRAD, text, image_bytes)
        results.append("✅ ДОМ ГРАНД TG" if success else "❌ ДОМ ГРАНД TG")
    except Exception as e:
        results.append(f"❌ ДОМ ГРАНД: {e}")
    
    # VK через Publisher
    try:
        success = await publisher.publish_to_vk(text, image_bytes)
        results.append("✅ VK" if success else "❌ VK")
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


@content_router.callback_query(F.data.startswith("pub_tg:"))
async def publish_tg_only(callback: CallbackQuery, state: FSMContext):
    """Централизованная публикация в Telegram через Publisher с подписью эксперта"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)

    if not post:
        await callback.answer("❌ Пост не найден")
        return

    # ── ЦЕНТРАЛИЗАЦИЯ: Используем единый сервис Publisher ───────────────────────────
    from services.publisher import publisher
    
    # Устанавливаем bot в publisher
    if not publisher.bot:
        publisher.bot = callback.bot

    text = ensure_quiz_and_hashtags(post['body']) + _get_expert_signature()
    results = []
    
    # Подготавливаем изображение
    image_bytes = None
    if post.get("image_url"):
        image_bytes = await download_photo(callback.bot, post["image_url"])
    
    try:
        # Публикуем в GEORIS через Publisher
        success_georis = await publisher.publish_to_telegram(CHANNEL_ID_GEORIS, text, image_bytes)
        results.append("✅ GEORIS" if success_georis else "❌ GEORIS")
        
        # Публикуем в ДОМ ГРАНД через Publisher
        success_dom_grad = await publisher.publish_to_telegram(CHANNEL_ID_DOM_GRAD, text, image_bytes)
        results.append("✅ ДОМ ГРАНД" if success_dom_grad else "❌ ДОМ ГРАНД")
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
    
    # Очищаем HTML для ВК; добавляем квиз и хэштеги (обязательно)
    text = clean_html_for_vk(post['body'])
    if VK_QUIZ_LINK not in text:
        text += f"\n\n📍 Пройти квиз: {VK_QUIZ_LINK}"
    if CONTENT_HASHTAGS and CONTENT_HASHTAGS.strip() and CONTENT_HASHTAGS.strip() not in text:
        text += f"\n\n{CONTENT_HASHTAGS.strip()}"
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


@content_router.callback_query(F.data.startswith("pub_all:"))
async def publish_all_channels(callback: CallbackQuery, state: FSMContext):
    """Публикация во все каналы: TG + VK"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)

    if not post:
        await callback.answer("❌ Пост не найден")
        return

    from services.publisher import publisher
    if not publisher.bot:
        publisher.bot = callback.bot

    text_tg = ensure_quiz_and_hashtags(post['body']) + _get_expert_signature()
    text_vk = clean_html_for_vk(post['body'])
    if VK_QUIZ_LINK not in text_vk:
        text_vk += f"\n\n📍 Пройти квиз: {VK_QUIZ_LINK}"
    if CONTENT_HASHTAGS and CONTENT_HASHTAGS.strip() and CONTENT_HASHTAGS.strip() not in text_vk:
        text_vk += f"\n\n{CONTENT_HASHTAGS.strip()}"

    image_bytes = None
    if post.get("image_url"):
        image_bytes = await download_photo(callback.bot, post["image_url"])

    results = []

    # TG
    try:
        success_georis = await publisher.publish_to_telegram(CHANNEL_ID_GEORIS, text_tg, image_bytes)
        results.append("✅ GEORIS" if success_georis else "❌ GEORIS")
        
        success_dom_grad = await publisher.publish_to_telegram(CHANNEL_ID_DOM_GRAD, text_tg, image_bytes)
        results.append("✅ ДОМ ГРАНД" if success_dom_grad else "❌ ДОМ ГРАНД")
    except Exception as e:
        results.extend([f"❌ TG: {e}"])

    # VK
    try:
        vk_id = await vk_publisher.post_with_photo(text_vk, image_bytes) if image_bytes else await vk_publisher.post_text_only(text_vk)
        vk_link = f"https://vk.com/wall-{VK_GROUP_ID}_{vk_id}" if vk_id else None
        results.append("✅ VK" if vk_id else "❌ VK")
    except Exception as e:
        results.append(f"❌ VK: {e}")

    await db.update_content_post(post_id, status="published")
    await callback.message.edit_text(f"✅ <b>Во все каналы:</b>\n" + "\n".join(results), reply_markup=get_back_btn(), parse_mode="HTML")
    
    # Финансовый лог
    cost = 4.00  # TG + VK
    await callback.bot.send_message(
        chat_id=LEADS_GROUP_CHAT_ID,
        text=f"💰 Пост #{post_id} опубликован во все каналы. Списано: {cost}₽"
    )
    
    await state.clear()


@content_router.callback_query(F.data.startswith("draft:"))
async def save_draft(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    try:
        kb = get_queue_keyboard(post_id)
        pub_date = post.get("publish_date")
        time_str = "12:00"
        if pub_date:
            try:
                from datetime import datetime as dt
                if hasattr(pub_date, "strftime"):
                    time_str = pub_date.strftime("%d.%m %H:%M")
                elif isinstance(pub_date, str):
                    # SQLite: "2026-02-15 12:00:00" или ISO
                    if "T" in pub_date:
                        d = dt.fromisoformat(pub_date.replace("Z", "+00:00"))
                    else:
                        d = dt.strptime(pub_date[:19], "%Y-%m-%d %H:%M:%S")
                    time_str = d.strftime("%d.%m %H:%M")
            except Exception:
                pass
        hint = f"\n\n🕐 <b>Время публикации:</b> {time_str}\n💡 Кнопки: 📤 Во все каналы | 🚀 GEORIS | 🏘 ДОМ ГРАНД | 📱 MAX | 🌐 VK"
        body = f"📝 <b>Черновик #{post_id}</b>\n\n{post['body']}{hint}"
        if post.get("image_url"):
            photo = await _photo_input_for_send(callback.bot, post["image_url"])
            if photo is not None:
                await callback.bot.send_photo(
                    LEADS_GROUP_CHAT_ID, photo, caption=body,
                    message_thread_id=THREAD_ID_DRAFTS, parse_mode="HTML", reply_markup=kb
                )
            else:
                await callback.bot.send_message(
                    LEADS_GROUP_CHAT_ID, body,
                    message_thread_id=THREAD_ID_DRAFTS, parse_mode="HTML", reply_markup=kb
                )
        else:
            await callback.bot.send_message(
                LEADS_GROUP_CHAT_ID, body,
                message_thread_id=THREAD_ID_DRAFTS, parse_mode="HTML", reply_markup=kb
            )
        
        await db.update_content_post(post_id, status="in_drafts")
        await callback.message.edit_text("✅ В черновиках (топик 85)", reply_markup=get_back_btn())
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}", reply_markup=get_back_btn())
    
    await state.clear()


class SchedulePostStates(StatesGroup):
    waiting_datetime = State()

@content_router.callback_query(F.data.startswith("schedule:"))
async def schedule_post_start(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split(":")[1])
    await state.update_data(schedule_post_id=post_id)
    from datetime import datetime, timedelta
    now = datetime.now()
    today_12 = now.replace(hour=12, minute=0, second=0, microsecond=0)
    tomorrow_10 = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    tomorrow_12 = (now + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Сегодня 12:00 ({today_12.strftime('%d.%m')})", callback_data=f"sched_quick:{post_id}:{today_12.strftime('%Y-%m-%d %H:%M')}")
    builder.button(text=f"Завтра 10:00 ({tomorrow_10.strftime('%d.%m')})", callback_data=f"sched_quick:{post_id}:{tomorrow_10.strftime('%Y-%m-%d %H:%M')}")
    builder.button(text=f"Завтра 12:00 ({tomorrow_12.strftime('%d.%m')})", callback_data=f"sched_quick:{post_id}:{tomorrow_12.strftime('%Y-%m-%d %H:%M')}")
    builder.button(text="✏️ Ввести вручную", callback_data=f"sched_manual:{post_id}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1)
    await callback.message.answer(f"⏰ <b>Запланировать пост #{post_id}</b>\n\nВыберите время:", reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@content_router.callback_query(F.data.startswith("sched_quick:"))
async def schedule_quick(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    post_id = int(parts[1])
    dt_str = parts[2] + ":" + parts[3]
    await _save_schedule(callback, post_id, dt_str)
    await state.clear()

@content_router.callback_query(F.data.startswith("sched_manual:"))
async def schedule_manual_start(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split(":")[1])
    await state.set_state(SchedulePostStates.waiting_datetime)
    await state.update_data(schedule_post_id=post_id)
    await callback.message.answer("✏️ Введите дату и время:\n<code>ДД.ММ ЧЧ:ММ</code>\n\nНапример: <code>20.03 14:30</code>", parse_mode="HTML")
    await callback.answer()

@content_router.message(SchedulePostStates.waiting_datetime)
async def schedule_manual_input(message, state: FSMContext):
    data = await state.get_data()
    post_id = data.get("schedule_post_id")
    try:
        from datetime import datetime
        dt = datetime.strptime(message.text.strip(), "%d.%m %H:%M").replace(year=datetime.now().year)
        await _save_schedule(message, post_id, dt.strftime("%Y-%m-%d %H:%M"), is_message=True)
        await state.clear()
    except ValueError:
        await message.answer("❌ Неверный формат. Пример: <code>20.03 14:30</code>", parse_mode="HTML")

async def _save_schedule(event, post_id: int, dt_str: str, is_message: bool = False):
    try:
        from datetime import datetime
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        await db.update_content_post(post_id, status="approved", publish_date=dt)
        text = f"✅ <b>Пост #{post_id} запланирован!</b>\n\n📅 Публикация: <b>{dt.strftime('%d.%m.%Y в %H:%M')}</b>\n\nБот опубликует автоматически."
        if is_message:
            await event.answer(text, parse_mode="HTML")
        else:
            await event.message.answer(text, parse_mode="HTML")
            await event.answer()
    except Exception as e:
        err = f"❌ Ошибка: {e}"
        if is_message:
            await event.answer(err)
        else:
            await event.answer(err)

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
    await callback.message.edit_text("🎯 <b>GEORIS Content Bot</b>", reply_markup=get_back_btn(), parse_mode="HTML")

@content_router.callback_query(F.data.startswith("queue_img_"))
async def queue_img_handler(callback: CallbackQuery):
    post_id = int(callback.data.split("_")[-1])
    await callback.answer("🎨 Генерирую обложку...")

    post = await db.get_content_post(post_id)
    if not post:
        await callback.message.answer("❌ Пост не найден")
        return

    # Строим промпт по содержимому поста
    body = post.get("body") or post.get("title") or "Перепланировка квартиры Москва"
    prompt = _build_cover_prompt(body)

    image_b64 = await _auto_generate_image(prompt)
    if not image_b64:
        await callback.message.answer("❌ Не удалось сгенерировать обложку")
        return

    try:
        image_bytes = base64.b64decode(image_b64)
        photo = BufferedInputFile(image_bytes, filename="cover.jpg")
        sent = await callback.message.answer_photo(
            photo=photo,
            caption=f"🖼 <b>Обложка для поста #{post_id}</b>",
            parse_mode="HTML"
        )
        # Сохраняем file_id — теперь при публикации картинка прикрепится автоматически
        if sent.photo:
            await db.update_content_plan_entry(post_id, image_url=sent.photo[-1].file_id)
            await callback.message.answer(
                f"✅ Обложка сохранена к посту #{post_id} и будет прикреплена при публикации.",
                reply_markup=get_back_btn()
            )
    except Exception as e:
        logger.error(f"queue_img send error: {e}")
        await callback.message.answer("❌ Ошибка отправки изображения")

@content_router.callback_query(F.data.startswith("queue_pub_"))
async def queue_pub_handler(callback: CallbackQuery):
    post_id = int(callback.data.split("_")[-1])
    await callback.answer("📢 Публикую пост...")
    from services.publisher import publisher
    from database import db

    post = await db.get_content_post(post_id)
    if post:
        text = ensure_quiz_and_hashtags(post.get('body', ''))
        image_bytes = await download_photo(callback.bot, post['image_url']) if post.get('image_url') else None
        results = await publisher.publish_all(text, image_bytes)
        await callback.message.answer(f"✅ Опубликовано! Результаты: {results}")
    else:
        await callback.answer("❌ Пост не найден")

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
    await message.answer("🎯 <b>GEORIS Content Bot</b>\n\nСоздание и публикация контента:\n• Telegram (GEORIS + ДОМ ГРАНД)\n• ВКонтакте (с кнопками)\n\nВыберите действие:", reply_markup=get_main_menu(), parse_mode="HTML")
    await state.set_state(ContentStates.main_menu)
