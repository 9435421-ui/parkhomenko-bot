import os
import logging
import aiohttp
import asyncio
import base64
from typing import Optional

logger = logging.getLogger(__name__)

class ImageGenerator:
    """Генерация обложек для постов"""
    
    def __init__(self):
        self.yandex_key = os.getenv('YANDEX_API_KEY')
        self.folder_id = os.getenv('FOLDER_ID')
        self.router_key = os.getenv('ROUTER_AI_KEY')
        self.use_yandex = bool(self.yandex_key and self.folder_id)
        
    async def generate_cover(self, title: str, style: str = "modern") -> Optional[bytes]:
        """
        Генерация обложки на основе заголовка
        """
        prompt = self._create_prompt(title, style)
        logger.info(f"🎨 Генерирую обложку для: {title} (стиль: {style})")
        
        if self.use_yandex:
            return await self._generate_yandex(prompt)
        else:
            # Fallback на Router AI (Gemini/OpenAI)
            return await self._generate_router(prompt)
    
    def _create_prompt(self, title: str, style: str) -> str:
        """Создание промпта для генерации"""
        base = f"Professional real estate cover image for a blog post. No text on image. {title}. "
        
        styles = {
            'modern': 'Modern Moscow architecture, clean lines, blue and white colors, professional architectural photography, high resolution, 4k',
            'classic': 'Classic Russian architecture, warm colors, elegant design, professional photography',
            'minimal': 'Minimalist design, white background, geometric shapes, clean composition'
        }
        
        return base + styles.get(style, styles['modern'])
    
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
                "messages": [{"text": prompt, "weight": 1}],
                "generationOptions": {
                    "seed": os.urandom(4).hex(),
                    "aspectRatio": {
                        "widthRatio": 1,
                        "heightRatio": 1
                    }
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload) as resp:
                    result = await resp.json()
                    operation_id = result.get('id')
                    
                if not operation_id:
                    logger.error(f"❌ Yandex Art: No operation ID in response: {result}")
                    return None
                
                # Ожидание результата
                for _ in range(30): # 60 секунд максимум
                    await asyncio.sleep(2)
                    op_url = f"https://llm.api.cloud.yandex.net/operations/{operation_id}"
                    async with session.get(op_url, headers=headers) as resp:
                        op_result = await resp.json()
                        if op_result.get('done'):
                            image_base64 = op_result.get('response', {}).get('image')
                            if image_base64:
                                return base64.b64decode(image_base64)
                            break
            
            return None
        except Exception as e:
            logger.error(f"❌ Yandex generation error: {e}")
            return None
    
    async def _generate_router(self, prompt: str) -> Optional[bytes]:
        """Генерация через Router AI (fallback)"""
        if not self.router_key:
            return None
            
        try:
            # Пример для Gemini 1.5 Pro через Router AI
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.router_key}",
                "Content-Type": "application/json"
            }
            
            # OpenRouter не генерирует изображения напрямую, 
            # но мы можем использовать модели типа DALL-E или Stable Diffusion если они доступны
            # Для примера оставим заглушку или используем конкретный эндпоинт если он есть
            logger.warning("⚠️ Router AI image generation not fully implemented")
            return None
        except Exception as e:
            logger.error(f"❌ Router AI generation error: {e}")
            return None
    
    async def generate_from_topic(self, topic: dict, style: str = "modern") -> Optional[bytes]:
        """Генерация на основе темы от CreativeAgent"""
        title = topic.get('title', '')
        if not title:
            title = topic.get('topic', 'Перепланировка квартиры')
        return await self.generate_cover(title, style)

# Singleton
image_generator = ImageGenerator()
