import os
import logging
import aiohttp
import base64
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

class ImageGenerator:
    """Генерация обложек через Yandex Art или Router AI (fallback)"""
    
    def __init__(self):
        self.yandex_key = os.getenv('YANDEX_API_KEY')
        self.folder_id = os.getenv('FOLDER_ID')
        # Router AI: генерация изображений (Nano Banana / OpenRouter), отдельный ключ опционален
        self.router_key = os.getenv('ROUTER_AI_IMAGE_KEY') or os.getenv('ROUTER_AI_KEY')
        
        # Проверяем доступность сервисов
        self.use_yandex = bool(self.yandex_key and self.folder_id)
        self.use_router = bool(self.router_key)
        
        if not self.use_yandex and not self.use_router:
            logger.warning("⚠️ Нет API ключей для генерации изображений!")
        
    async def generate_cover(self, title: str, style: str = "modern") -> Optional[bytes]:
        """
        Генерация обложки с fallback на Router AI
        """
        prompt = self._create_prompt(title, style)
        
        # Пробуем Yandex Art первым
        if self.use_yandex:
            try:
                result = await self._generate_yandex(prompt)
                if result:
                    return result
                logger.warning("Yandex Art не сработал, пробуем Router AI...")
            except Exception as e:
                logger.error(f"Yandex Art ошибка: {e}")
        
        # Fallback на Router AI
        if self.use_router:
            try:
                return await self._generate_router(prompt)
            except Exception as e:
                logger.error(f"Router AI ошибка: {e}")
        
        return None
    
    def _create_prompt(self, title: str, style: str) -> str:
        """Создание промпта. Короткий промпт снижает риск 400 от Yandex Art. 401 = неверный API-ключ."""
        # Упрощённый промпт: без кавычек и длинных фраз (меньше 400 ошибок)
        safe_title = (title or "real estate")[:60].replace('"', "'").strip()
        base = f"Real estate cover, {safe_title}. "
        styles = {
            'modern': 'Modern architecture, minimalist, blue and white, professional photo.',
            'classic': 'Classic architecture, warm colors, professional photo.',
            'minimal': 'Minimalist white background, clean design.'
        }
        no_text = " No text, no words, no letters. Image only."
        return base + styles.get(style, styles['modern']) + no_text
    
    async def _generate_yandex(self, prompt: str) -> Optional[bytes]:
        """Генерация через Yandex Art"""
        try:
            url = "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync"
            
            headers = {
                "Authorization": f"Api-Key {self.yandex_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "modelUri": f"art://{self.folder_id}/yandex-art/latest",
                "messages": [
                    {
                        "text": prompt,
                        "weight": 1.0
                    }
                ],
                "generationOptions": {
                    "seed": 42,
                    "aspectRatio": {
                        "widthRatio": 16,
                        "heightRatio": 9
                    }
                }
            }
            
            async with aiohttp.ClientSession() as session:
                # Отправляем запрос
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"Yandex Art HTTP {resp.status}: {text[:200]}")
                        if resp.status == 401:
                            logger.error("Yandex Art 401: проверьте YANDEX_API_KEY и FOLDER_ID в .env")
                        elif resp.status == 400:
                            logger.error("Yandex Art 400: промпт упрощён в _create_prompt; при повторе — укоротите тему.")
                        return None
                    
                    result = await resp.json()
                    operation_id = result.get('id')
                    
                    if not operation_id:
                        logger.error(f"Yandex Art: нет operation_id в ответе: {result}")
                        return None
                    
                    # Ждем результат
                    return await self._get_yandex_result(session, operation_id, headers)
                    
        except Exception as e:
            logger.error(f"Yandex Art exception: {e}")
            return None
    
    async def _get_yandex_result(self, session, operation_id: str, headers: dict, max_attempts: int = 30) -> Optional[bytes]:
        """Получение результата генерации"""
        url = f"https://llm.api.cloud.yandex.net/operations/{operation_id}"
        
        for attempt in range(max_attempts):
            try:
                async with session.get(url, headers=headers) as resp:
                    result = await resp.json()
                    
                    if result.get('done'):
                        if 'response' in result and 'image' in result['response']:
                            # Декодируем base64
                            image_data = base64.b64decode(result['response']['image'])
                            logger.info(f"✅ Yandex Art: изображение сгенерировано ({len(image_data)} bytes)")
                            return image_data
                        elif 'error' in result:
                            logger.error(f"Yandex Art operation error: {result['error']}")
                            return None
                    
                    # Ждем перед следующей попыткой
                    await asyncio.sleep(2)
                    
            except Exception as e:
                logger.error(f"Yandex Art polling error: {e}")
                await asyncio.sleep(2)
        
        logger.error("Yandex Art: timeout waiting for result")
        return None
    
    async def _generate_router(self, prompt: str) -> Optional[bytes]:
        """
        Fallback генерация через Router AI (NaNa Banana / ChatGPT Mini)
        Используем модель для генерации изображений
        """
        try:
            # OpenRouter / Router AI images endpoint
            url = "https://openrouter.ai/api/v1/images/generations"
            
            headers = {
                "Authorization": f"Bearer {self.router_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "openai/dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": "1024x1024"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"Router AI HTTP {resp.status}: {text[:200]}")
                        return None
                    
                    result = await resp.json()
                    
                    # Получаем URL изображения
                    if 'data' in result and len(result['data']) > 0:
                        image_url = result['data'][0].get('url')
                        if image_url:
                            # Скачиваем изображение
                            async with session.get(image_url) as img_resp:
                                if img_resp.status == 200:
                                    image_data = await img_resp.read()
                                    logger.info(f"✅ Router AI: изображение сгенерировано ({len(image_data)} bytes)")
                                    return image_data
                    
                    logger.error(f"Router AI: нет изображения в ответе: {result}")
                    return None
                    
        except Exception as e:
            logger.error(f"Router AI exception: {e}")
            return None
    
    async def generate_from_topic(self, topic: dict, style: str = "modern") -> Optional[bytes]:
        """Генерация на основе темы от CreativeAgent"""
        title = topic.get('title', '')
        if not title:
            title = topic.get('topic', 'Перепланировка')
        
        logger.info(f"🎨 Генерирую обложку для: {title} (стиль: {style})")
        return await self.generate_cover(title, style)

# Singleton
image_generator = ImageGenerator()


# === Функция с Retry логикой и финансовым расчетом ===

async def generate_creative(payload: str, attempt: int = 1) -> tuple:
    """
    Генерация с retry логикой и финансовым расчетом.
    
    Returns:
        tuple: (image_url, cost, service_name)
    """
    from utils import router_ai
    
    # Пытаемся через Router API (Nano Banana)
    try:
        logger.info(f"🎨 Генерация через Router AI (попытка {attempt})...")
        # Используем router_ai для генерации
        response = await router_ai.generate_response(
            user_prompt=f"Generate image: {payload}. No text, no words, no letters, no captions — image only.",
            max_tokens=2000
        )
        
        # Если получили URL изображения
        if response and "http" in response:
            cost = 2.50  # Рублей за генерацию
            return response, cost, "Router (Banana)"
        
        raise Exception("Router AI не вернул изображение")
    
    except Exception as e:
        logger.error(f"❌ Router AI ошибка: {e}")
        
        if attempt == 1:
            # Сбой — ждем 5 сек и переключаем на Яндекс
            logger.warning("⚠️ Сбой Router. Перехожу на Яндекс АРТ...")
            await asyncio.sleep(5)
            return await generate_yandex_creative(payload)

    # Если не удалось — возвращаем None
    return None, 0, "Failed"


async def generate_yandex_creative(payload: str) -> tuple:
    """
    Резервный канал (Яндекс АРТ)
    """
    try:
        logger.info("🎨 Генерация через Яндекс АРТ...")
        
        # Используем image_generator
        image_data = await image_generator.generate_cover(payload, style="modern")
        
        if image_data:
            cost = 1.80  # Рублей за генерацию
            # Возвращаем base64 как URL (для совместимости)
            import base64
            b64 = base64.b64encode(image_data).decode()
            return f"data:image/jpeg;base64,{b64}", cost, "Yandex ART"
        
        raise Exception("Yandex Art не сгенерировал изображение")
        
    except Exception as e:
        logger.error(f"❌ Yandex ART ошибка: {e}")
        return None, 0, "Yandex ART Failed"
