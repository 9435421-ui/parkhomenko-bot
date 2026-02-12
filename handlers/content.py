"""
Content Handler — TERION Ecosystem (RouterAI + YandexART Edition)
TG + VK публикация, AI-генерация контента
"""
from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, KeyboardButton, FSInputFile
)
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from PIL import Image
import logging
import aiohttp
import json
import base64
import os
import tempfile
import io
import asyncio
from datetime import datetime, timedelta
from typing import Optional

from database import db
from config import (
    CONTENT_BOT_TOKEN,
    TERION_CHANNEL_ID,
    DOM_GRAND_CHANNEL_ID,
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
    """RouterAI для текстов и Gemini Image"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def generate(self, prompt: str, model: str = "quin", max_tokens: int = 2000) -> Optional[str]:
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
        """Генерация изображения через Gemini 2.5 Flash Image"""
        payload = {
            "model": "gemini-2.5-flash-image",
            "messages": [{
                "role": "user",
                "content": f"Generate image: {prompt}. Professional architectural photography style."
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
                        # Парсим base64 если есть
                        if "data:image" in content:
                            import re
                            match = re.search(r'data:image/[^;]+;base64,([^"\']+)', content)
                            if match:
                                return match.group(1)
                        return content
        except Exception as e:
            logger.error(f"Gemini Image error: {e}")
        return None


# Инициализация клиентов
yandex_art = YandexArtClient(YANDEX_API_KEY, FOLDER_ID)
router_ai = RouterAIClient(ROUTER_AI_KEY)


# === VK PUBLISHER ===

class VKPublisher:
    """Публикация в ВКонтакте с кнопками"""
    
    def __init__(self, token: str, group_id: int):
        self.token = token
        self.group_id = group_id
        self.api_version = "5.199"
    
    async def _make_request(self, method: str, params: dict) -> Optional[dict]:
        """Запрос к API VK"""
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
        # Получаем URL для загрузки
        upload_data = await self._make_request("photos.getWallUploadServer", {"group_id": self.group_id})
        if not upload_data:
            return None
        
        upload_url = upload_data.get("upload_url")
        if not upload_url:
            return None
        
        # Загружаем файл
        try:
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field("photo", image_data, filename="photo.jpg", content_type="image/jpeg")
                
                async with session.post(upload_url, data=form) as resp:
                    result = await resp.json()
                    
                    if "error" in result:
                        return None
                    
                    # Сохраняем фото
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
    
    async def create_buttons(self) -> str:
        """Создание кнопок для поста ВК"""
        buttons = {
            "inline": True,
            "buttons": [
                [{"action": {"type": "open_link", "link": "https://t.me/terion_bot?start=quiz", "label": "📝 Пройти квиз"}}],
                [{"action": {"type": "open_link", "link": "https://t.me/terion_bot?start=consult", "label": "💬 Бесплатная консультация"}}]
            ]
        }
        return json.dumps(buttons, ensure_ascii=False)
    
    async def post_to_wall(self, message: str, photo_id: Optional[str] = None) -> Optional[int]:
        """Публикация поста на стену"""
        attachments = [photo_id] if photo_id else []
        
        params = {
            "owner_id": -self.group_id,
            "from_group": 1,
            "message": message,
            "attachments": ",".join(attachments),
            "keyboard": await self.create_buttons()
        }
        
        result = await self._make_request("wall.post", params)
        return result.get("post_id") if result else None
    
    async def post_text_only(self, message: str) -> Optional[int]:
        """Только текст"""
        return await self.post_to_wall(message, None)
    
    async def post_with_photo(self, message: str, image_bytes: bytes) -> Optional[int]:
        """С фото"""
        photo_id = await self.upload_photo(image_bytes)
        if not photo_id:
            return await self.post_text_only(message)
        return await self.post_to_wall(message, photo_id)


# Инициализация VK
vk_publisher = VKPublisher(VK_TOKEN, VK_GROUP_ID)


# === FSM STATES ===

class ContentStates(StatesGroup):
    main_menu = State()
    photo_topic = State()        # Тема перед загрузкой фото
    photo_upload = State()     # Загрузка фото
    preview_mode = State()     # Превью перед публикацией
    ai_text = State()          # Генерация текста
    ai_series = State()        # Серия постов
    ai_visual_select = State() # Выбор модели (Яндекс/Gemini)
    ai_visual_prompt = State() # Ввод промпта для изображения
    ai_plan = State()          # Контент-план
    ai_news = State()          # Новости
    edit_post = State()        # Редактирование


# === KEYBOARDS ===

def get_main_menu() -> ReplyKeyboardMarkup:
    """Главное меню"""
    kb = [
        [KeyboardButton(text="📸 Фото → Описание → Пост")],
        [KeyboardButton(text="🎨 ИИ-Визуал"), KeyboardButton(text="📅 Серия постов")],
        [KeyboardButton(text="📰 Новость"), KeyboardButton(text="📋 Контент-план")],
        [KeyboardButton(text="📝 Быстрый текст")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_preview_keyboard(post_id: int, has_image: bool = False) -> InlineKeyboardMarkup:
    """Превью перед публикацией"""
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

async def download_photo(bot: Bot, file_id: str) -> Optional[bytes]:
    """Скачать фото"""
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
    """Сжатие изображения"""
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


async def show_preview(message: Message, text: str, image_file_id: Optional[str] = None, post_id: Optional[int] = None):
    """Показать превью поста"""
    if not post_id:
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
            caption=f"👁 <b>Предпросмотр</b>\n\n{text[:700]}...",
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"👁 <b>Предпросмотр</b>\n\n{text[:700]}...",
            reply_markup=kb,
            parse_mode="HTML"
        )
    return post_id


# === GLOBAL MENU HANDLER ===

@content_router.message(F.text.in_([
    "📸 Фото → Описание → Пост",
    "🎨 ИИ-Визуал",
    "📅 Серия постов",
    "📰 Новость",
    "📋 Контент-план",
    "📝 Быстрый текст"
]))
async def global_menu_handler(message: Message, state: FSMContext):
    """Глобальный обработчик меню — работает всегда"""
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
    """Начало с фото — сначала тема"""
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
    """Получили тему → просим фото"""
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
    """Обработка фото с AI-анализом"""
    data = await state.get_data()
    topic = data.get('photo_topic', 'Перепланировка')
    
    photo = message.photo[-1]
    file_id = photo.file_id
    
    await message.answer(
        f"🔍 <b>Анализирую фото...</b>\n"
        f"Тема: {topic}",
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
    
    # Экспертный промпт
    prompt = (
        f"Ты — эксперт по перепланировкам. Тема: «{topic}»\n\n"
        f"Проанализируй фото и напиши пост:\n"
        f"1. <b>Заголовок</b> — конкретный, без фантастики\n"
        f"2. <b>Описание</b> — что на фото, особенности\n"
        f"3. <b>Экспертный комментарий</b> — нюансы перепланировки\n"
        f"4. <b>Важно</b> — юридические/технические моменты\n"
        f"5. <b>Призыв</b> — консультация\n\n"
        f"Без обещаний 'за 3 дня'. Реальные сроки. 400-700 знаков."
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
    
    # Добавляем квиз-ссылку если нет
    if VK_QUIZ_LINK not in description:
        description += f"\n\n📍 <a href='{VK_QUIZ_LINK}'>Пройти квиз</a>"
    
    post_id = await db.add_content_post(
        title=f"Фото: {topic[:40]}",
        body=description,
        image_url=file_id,
        channel="photo_workflow",
        status="preview"
    )
    
    await state.update_data(post_id=post_id, description=description, file_id=file_id, image_bytes=image_bytes)
    
    await message.answer_photo(
        photo=file_id,
        caption=f"👁 <b>Предпросмотр</b>\n\n{description[:700]}...",
        reply_markup=get_preview_keyboard(post_id, True),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.preview_mode)


# === 🎨 ИИ-ВИЗУАЛ (выбор модели) ===

async def visual_select_model(message: Message, state: FSMContext):
    """Выбор модели для генерации"""
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
    """Выбрана модель"""
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
    """Генерация изображения"""
    data = await state.get_data()
    model = data.get('visual_model', 'yandex')
    user_prompt = message.text
    
    await message.answer(
        f"⏳ <b>Генерация...</b>\n"
        f"Модель: {'Яндекс АРТ' if model == 'yandex' else 'Gemini Nano'}",
        parse_mode="HTML"
    )
    
    # Улучшаем промпт
    enhanced = f"{user_prompt}, professional architectural photography, interior design, high quality, detailed, no text, no watermarks"
    
    # Генерация
    image_b64 = None
    if model == 'yandex':
        image_b64 = await yandex_art.generate(enhanced)
    else:
        image_b64 = await router_ai.generate_image_gemini(enhanced)
    
    if not image_b64:
        await message.answer(
            "❌ Ошибка генерации. Попробуйте другую модель или описание.",
            reply_markup=get_main_menu()
        )
        await state.clear()
        return
    
    # Отправляем
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
        logger.error(f"Send image error: {e}")
        await message.answer("❌ Ошибка отправки", reply_markup=get_main_menu())
    
    await state.clear()


@content_router.callback_query(F.data == "visual_back")
async def visual_back(callback: CallbackQuery, state: FSMContext):
    """Назад к выбору модели"""
    await callback.answer()
    await visual_select_model(callback.message, state)


# === 📅 СЕРИЯ ПОСТОВ ===

async def series_start(message: Message, state: FSMContext):
    """Серия постов"""
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
    """Генерация серии"""
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
        f"Формат: День N: Заголовок\nТекст 80-120 слов\nПризыв к действию"
    )
    
    result = await router_ai.generate(prompt, max_tokens=4000)
    
    if not result:
        await message.answer("❌ Ошибка", reply_markup=get_main_menu())
        await state.clear()
        return
    
    post_id = await db.add_content_post(
        title=f"Серия {days} дней: {topic[:40]}",
        body=result,
        channel="series",
        status="draft"
    )
    
    # Отправляем в черновики
    await message.bot.send_message(
        chat_id=LEADS_GROUP_CHAT_ID,
        message_thread_id=THREAD_ID_DRAFTS,
        text=f"📅 <b>Серия {days} дней</b>\n\n<b>Тема:</b> {topic}\n\n{result[:1500]}...",
        parse_mode="HTML"
    )
    
    # Спрашиваем про изображения
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
    """Генерация обложек для серии"""
    parts = callback.data.split(":")
    model = parts[1]
    topic = parts[2]
    days = int(parts[3])
    
    await callback.answer("🎨 Генерация...")
    await callback.message.edit_text(
        f"⏳ <b>Генерация {days} обложек...</b>\n"
        f"Модель: {'Яндекс АРТ' if model == 'yandex' else 'Gemini Nano'}",
        parse_mode="HTML"
    )
    
    for i in range(1, days + 1):
        art_prompt = f"{topic}, день {i}, перепланировка, professional interior, modern design, no text"
        
        await callback.message.answer(f"🎨 <b>День {i}...</b>", parse_mode="HTML")
        
        if model == 'yandex':
            image_b64 = await yandex_art.generate(art_prompt)
        else:
            image_b64 = await router_ai.generate_image_gemini(art_prompt)
        
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
    
    await callback.message.answer(
        "✅ <b>Все обложки готовы!</b>",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )


# === 📋 КОНТЕНТ-ПЛАН ===

async def plan_start(message: Message, state: FSMContext):
    """Контент-план"""
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
    """Генерация плана"""
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
        f"Для каждого дня: заголовок, содержание (2-3 предл), формат."
    )
    
    plan = await router_ai.generate(prompt, max_tokens=3000)
    
    if not plan:
        await message.answer("❌ Ошибка", reply_markup=get_main_menu())
        await state.clear()
        return
    
    await message.bot.send_message(
        chat_id=LEADS_GROUP_CHAT_ID,
        message_thread_id=THREAD_ID_CONTENT_PLAN,
        text=f"📋 <b>План {days} дней</b>\n\n<b>Тема:</b> {topic}\n\n{plan}",
        parse_mode="HTML"
    )
    
    # Спрашиваем про арты
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
    await state.set_state(ContentStates.ai_news)


@content_router.message(ContentStates.ai_news)
async def ai_news_handler(message: Message, state: FSMContext):
    """Генерация новости"""
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
        await message.answer("❌ Ошибка", reply_markup=get_main_menu())
        await state.clear()
        return
    
    # Добавляем квиз
    if VK_QUIZ_LINK not in news:
        news += f"\n\n📍 <a href='{VK_QUIZ_LINK}'>Пройти квиз</a>"
    
    post_id = await show_preview(message, news)
    await state.set_state(ContentStates.preview_mode)
    await state.update_data(post_id=post_id, text=news)


# === 📝 БЫСТРЫЙ ТЕКСТ ===

async def quick_start(message: Message, state: FSMContext):
    """Быстрый текст"""
    await message.answer(
        "📝 <b>Быстрый текст</b>\n\n"
        "Введите тему:",
        reply_markup=get_back_btn(),
        parse_mode="HTML"
    )
    await state.set_state(ContentStates.ai_text)


@content_router.message(ContentStates.ai_text)
async def ai_text_handler(message: Message, state: FSMContext):
    """Генерация текста"""
    topic = message.text
    
    await message.answer("⏳ <b>Пишу...</b>", parse_mode="HTML")
    
    prompt = (
        f"Пост для TG на тему «{topic}». "
        f"Экспертный, живой стиль. 100-150 слов. "
        f"Эмодзи + призыв к консультации."
    )
    
    text = await router_ai.generate(prompt)
    
    if not text:
        await message.answer("❌ Ошибка", reply_markup=get_main_menu())
        await state.clear()
        return
    
    # Добавляем квиз
    if VK_QUIZ_LINK not in text:
        text += f"\n\n📍 <a href='{VK_QUIZ_LINK}'>Пройти квиз</a> @terion_bot"
    
    post_id = await show_preview(message, text)
    await state.set_state(ContentStates.preview_mode)
    await state.update_data(post_id=post_id, text=text)


# === ПУБЛИКАЦИЯ ===

@content_router.callback_query(F.data.startswith("pub_all:"))
async def publish_all(callback: CallbackQuery, state: FSMContext):
    """Публикация везде: TG + VK"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    if not post:
        await callback.answer("❌ Пост не найден")
        return
    
    await callback.answer("🚀 Публикую...")
    
    # Добавляем квиз если нет
    text = post['body']
    if VK_QUIZ_LINK not in text:
        text += f"\n\n📍 <a href='{VK_QUIZ_LINK}'>Пройти квиз</a>"
    
    results = []
    
    # TG TERION
    try:
        if post.get("image_url"):
            await callback.bot.send_photo(TERION_CHANNEL_ID, post["image_url"], text, parse_mode="HTML")
        else:
            await callback.bot.send_message(TERION_CHANNEL_ID, text, parse_mode="HTML")
        results.append("✅ TERION TG")
    except Exception as e:
        results.append(f"❌ TERION: {e}")
    
    # TG ДОМ ГРАНД
    try:
        if post.get("image_url"):
            await callback.bot.send_photo(DOM_GRAND_CHANNEL_ID, post["image_url"], text, parse_mode="HTML")
        else:
            await callback.bot.send_message(DOM_GRAND_CHANNEL_ID, text, parse_mode="HTML")
        results.append("✅ ДОМ ГРАНД TG")
    except Exception as e:
        results.append(f"❌ ДОМ ГРАНД: {e}")
    
    # VK
    try:
        image_bytes = None
        if post.get("image_url"):
            # Скачиваем для VK
            image_bytes = await download_photo(callback.bot, post["image_url"])
        
        if image_bytes:
            vk_id = await vk_publisher.post_with_photo(text, image_bytes)
        else:
            vk_id = await vk_publisher.post_text_only(text)
        
        results.append(f"✅ VK (post{vk_id})" if vk_id else "❌ VK")
    except Exception as e:
        results.append(f"❌ VK: {e}")
    
    await db.update_content_post(post_id, status="published")
    
    # Лог в рабочую группу
    await callback.bot.send_message(
        chat_id=LEADS_GROUP_CHAT_ID,
        message_thread_id=THREAD_ID_LOGS,
        text=f"🚀 <b>Публикация #{post_id}</b>\n\n" + "\n".join(results),
        parse_mode="HTML"
    )
    
    await callback.message.edit_text(
        f"✅ <b>Опубликовано!</b>\n\n" + "\n".join(results),
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )
    await state.clear()


@content_router.callback_query(F.data.startswith("pub_tg:"))
async def publish_tg_only(callback: CallbackQuery, state: FSMContext):
    """Только Telegram"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    text = post['body']
    if VK_QUIZ_LINK not in text:
        text += f"\n\n📍 <a href='{VK_QUIZ_LINK}'>Пройти квиз</a>"
    
    results = []
    
    try:
        if post.get("image_url"):
            await callback.bot.send_photo(TERION_CHANNEL_ID, post["image_url"], text, parse_mode="HTML")
            await callback.bot.send_photo(DOM_GRAND_CHANNEL_ID, post["image_url"], text, parse_mode="HTML")
        else:
            await callback.bot.send_message(TERION_CHANNEL_ID, text, parse_mode="HTML")
            await callback.bot.send_message(DOM_GRAND_CHANNEL_ID, text, parse_mode="HTML")
        results = ["✅ TERION", "✅ ДОМ ГРАНД"]
    except Exception as e:
        results = [f"❌ {e}"]
    
    await db.update_content_post(post_id, status="published")
    await callback.message.edit_text(
        f"✅ <b>TG:</b>\n" + "\n".join(results),
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )
    await state.clear()


@content_router.callback_query(F.data.startswith("pub_vk:"))
async def publish_vk_only(callback: CallbackQuery, state: FSMContext):
    """Только VK"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    text = post['body']
    if VK_QUIZ_LINK not in text:
        text += f"\n\n📍 <a href='{VK_QUIZ_LINK}'>Пройти квиз</a>"
    
    try:
        image_bytes = None
        if post.get("image_url"):
            image_bytes = await download_photo(callback.bot, post["image_url"])
        
        if image_bytes:
            vk_id = await vk_publisher.post_with_photo(text, image_bytes)
        else:
            vk_id = await vk_publisher.post_text_only(text)
        
        await db.update_content_post(post_id, status="published")
        await callback.message.edit_text(
            f"✅ <b>VK:</b> post{vk_id}" if vk_id else "❌ Ошибка VK",
            reply_markup=get_main_menu(),
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}", reply_markup=get_main_menu())
    
    await state.clear()


@content_router.callback_query(F.data.startswith("draft:"))
async def save_draft(callback: CallbackQuery, state: FSMContext):
    """В черновики"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    try:
        if post.get("image_url"):
            await callback.bot.send_photo(
                LEADS_GROUP_CHAT_ID,
                post["image_url"],
                f"📝 <b>Черновик #{post_id}</b>\n\n{post['body']}",
                message_thread_id=THREAD_ID_DRAFTS,
                parse_mode="HTML"
            )
        else:
            await callback.bot.send_message(
                LEADS_GROUP_CHAT_ID,
                f"📝 <b>Черновик #{post_id}</b>\n\n{post['body']}",
                message_thread_id=THREAD_ID_DRAFTS,
                parse_mode="HTML"
            )
        
        await db.update_content_post(post_id, status="in_drafts")
        await callback.message.edit_text("✅ В черновиках (топик 85)", reply_markup=get_main_menu())
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}", reply_markup=get_main_menu())
    
    await state.clear()


@content_router.callback_query(F.data.startswith("edit:"))
async def edit_handler(callback: CallbackQuery, state: FSMContext):
    """Редактирование"""
    post_id = int(callback.data.split(":")[1])
    post = await db.get_content_post(post_id)
    
    if not post:
        await callback.answer("❌ Не найден")
        return
    
    await state.update_data(edit_post_id=post_id)
    await callback.message.answer(
        f"✏️ <b>Редактирование #{post_id}</b>\n\n"
        f"Текущий текст:\n{post['body'][:500]}...\n\n"
        f"Введите новый текст:",
        parse_mode="HTML"
    )
    await callback.answer()
    await state.set_state(ContentStates.edit_post)


@content_router.message(ContentStates.edit_post)
async def edit_post_handler(message: Message, state: FSMContext):
    """Сохранение редактирования"""
    data = await state.get_data()
    post_id = data.get("edit_post_id")
    
    if post_id:
        await db.update_content_post(post_id, body=message.text)
        await message.answer("✅ Обновлено!", reply_markup=get_main_menu())
    
    await state.clear()


@content_router.callback_query(F.data == "cancel")
async def cancel_handler(callback: CallbackQuery, state: FSMContext):
    """Отмена"""
    await callback.answer("❌ Отменено")
    await state.clear()
    await callback.message.edit_text("❌ Отменено", reply_markup=get_main_menu())


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


# === ОБРАБОТКА ОШИБОК ===

@content_router.message(ContentStates.photo_upload)
async def wrong_photo(message: Message):
    """Если прислали не фото"""
    await message.answer("❌ Пожалуйста, отправьте фото или нажмите «Назад»")


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
