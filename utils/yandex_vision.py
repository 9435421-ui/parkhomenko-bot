"""
Яндекс Vision API для анализа изображений.
Используется для описания фото объектов недвижимости.
"""
import os
import base64
import logging
from typing import Optional
import aiohttp

logger = logging.getLogger(__name__)


class YandexVision:
    """Клиент Яндекс Vision API"""
    
    def __init__(self):
        self.api_key = os.getenv("YANDEX_API_KEY")
        self.folder_id = os.getenv("FOLDER_ID")
        self.endpoint = "https://vision.api.cloud.yandex.net/vision/v1/analyze"
    
    async def analyze_image(self, image_path: str) -> str:
        """
        Анализирует изображение и возвращает описание.
        
        Args:
            image_path: Путь к изображению
        
        Returns:
            str: Описание того что на фото
        """
        if not self.api_key or not self.folder_id:
            logger.warning("Yandex Vision не настроен (нет YANDEX_API_KEY или FOLDER_ID)")
            return "📸 Фото объекта"
        
        try:
            # Читаем и кодируем изображение
            with open(image_path, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode('utf-8')
            
            headers = {
                "Authorization": f"Api-Key {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "folderId": self.folder_id,
                "analyzeSpecs": [
                    {
                        "content": image_data,
                        "features": [
                            {
                                "type": "CLASSIFICATION",
                                "classificationSpecs": {
                                    "model": "moderation"
                                }
                            },
                            {
                                "type": "TEXT_DETECTION"
                            }
                        ]
                    }
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return self._parse_result(result)
                    else:
                        logger.error(f"Yandex Vision error: {response.status}")
                        return "📸 Фото объекта"
                        
        except Exception as e:
            logger.error(f"Yandex Vision error: {e}")
            return "📸 Фото объекта"
    
    def _parse_result(self, result: dict) -> str:
        """Парсит результат анализа"""
        try:
            # Извлекаем текст из изображения
            text_results = result.get('results', [])
            if text_results:
                for spec in text_results.get('results', []):
                    text_detection = spec.get('textDetection', {})
                    full_text = text_detection.get('fullTextAnnotation', '')
                    if full_text:
                        # Если есть текст на фото - возвращаем его
                        return f"📸 На фото: {full_text[:200]}"
            
            return "📸 Фото объекта недвижимости"
            
        except Exception as e:
            logger.error(f"Parse error: {e}")
            return "📸 Фото объекта"


async def analyze_photo(image_path: str) -> str:
    """Анализирует фото и возвращает описание"""
    vision = YandexVision()
    return await vision.analyze_image(image_path)


# Singleton
yandex_vision = YandexVision()
