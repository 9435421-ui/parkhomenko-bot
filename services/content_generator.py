"""
services/content_generator.py
Генерация экспертного контента по теме видео через Яндекс GPT
"""

import os
import logging
import aiohttp
from typing import Optional

logger = logging.getLogger(__name__)

class ContentGenerator:
    """Генерация экспертного контента"""
    
    def __init__(self, yandex_api_key: str = None):
        self.yandex_key = yandex_api_key or os.getenv('YANDEX_API_KEY')
        self.folder_id = os.getenv('YANDEX_FOLDER_ID', 'b1gvlt9doma4ddofm6v6')
        self.yandex_api = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    
    async def generate_expert_text(
        self, 
        topic: str,
        style: str = "expert"
    ) -> Optional[str]:
        """
        Генерировать экспертный текст по теме видео
        
        Args:
            topic: тема видео (например: "Согласование перепланировки")
            style: стиль (expert, simple, detailed)
        
        Returns:
            Сгенерированный текст или None
        """
        
        if not self.yandex_key:
            logger.warning("⚠️ YANDEX_API_KEY не задан")
            return None
        
        try:
            # Формируем промпт в зависимости от стиля
            if style == "expert":
                prompt = f"""Напиши короткий экспертный пост (150-200 слов) на тему: "{topic}"

Требования:
- Профессиональный тон
- Практические советы
- Релевантно для Москвы и МЖИ
- Включи CTА: "Пройти квиз"
- Включи хэштеги: #ГЕОРИС #перепланировка #согласование

Ответь ТОЛЬКО текстом поста, без заголовка."""
            
            elif style == "simple":
                prompt = f"""Напиши простой понятный пост (100-150 слов) на тему: "{topic}"

Требования:
- Разговорный тон
- Легко для понимания
- Практический совет
- Включи CTА: "Пройти квиз"

Ответь ТОЛЬКО текстом поста."""
            
            else:  # detailed
                prompt = f"""Напиши подробный пост (250-300 слов) на тему: "{topic}"

Требования:
- Детальное объяснение
- Список шагов/советов
- Ссылка на закон/норматив если есть
- Включи CTА: "Пройти квиз"
- Хэштеги: #ГЕОРИС #перепланировка

Ответь ТОЛЬКО текстом поста."""
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Api-Key {self.yandex_key}"
            }
            
            payload = {
                "modelUri": f"gpt://{self.folder_id}/yandexgpt/latest",
                "completionOptions": {
                    "stream": False,
                    "temperature": 0.7,
                    "maxTokens": "500"
                },
                "messages": [
                    {
                        "role": "user",
                        "text": prompt
                    }
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.yandex_api,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"❌ Yandex API error ({resp.status}): {error_text}")
                        return None
                    
                    result = await resp.json()
                    
                    # Извлекаем текст из ответа
                    if 'result' in result and 'alternatives' in result['result']:
                        text = result['result']['alternatives'][0]['message']['text']
                        logger.info(f"✅ Контент сгенерирован по теме: {topic}")
                        return text.strip()
                    else:
                        logger.warning("⚠️ Неправильный формат ответа от Yandex")
                        return None
        
        except Exception as e:
            logger.error(f"❌ Ошибка генерации контента: {e}")
            return None
    
    async def generate_caption(self, topic: str) -> str:
        """Генерировать короткую подпись для видео"""
        caption = f"<b>{topic}</b>\n\n📍 Пройти квиз\n\n#ГЕОРИС #перепланировка"
        return caption

# Инициализируем генератор
generator = ContentGenerator()
