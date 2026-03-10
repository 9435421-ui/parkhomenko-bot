"""
ImageAgent - генерация изображений для постов
"""
import os
import logging
import aiohttp
from typing import Optional

logger = logging.getLogger(__name__)


class ImageAgent:
    """Агент для генерации изображений через YandexGPT или внешний API"""
    
    def __init__(self, api_key: Optional[str] = None, folder_id: Optional[str] = None):
        """
        Инициализация ImageAgent
        """
        from services.image_generator import image_generator
        self.generator = image_generator
    
    def build_image_prompt(self, post_type: str, text: str) -> str:
        """
        Формирует детальный промпт на основе готового текста поста.
        Картинка (планировки, ЖК Москвы) должна строго соответствовать смыслу.
        """
        base_style = "Photorealistic, professional architectural photography, high quality, 8k, highly detailed. "
        
        # Анализируем текст для извлечения контекста (ЖК, тип помещения)
        context = ""
        if "ЖК" in text:
            # Пытаемся выцепить название ЖК (упрощенно)
            words = text.split()
            for i, word in enumerate(words):
                if word == "ЖК" and i + 1 < len(words):
                    context = f"in Moscow residential complex {words[i+1]}, "
                    break

        prompts = {
            'news': f"Modern Moscow architecture, {context}legal documents on a desk, blueprints, professional lighting.",
            'fact': f"Detailed floor plan analysis, magnifying glass over architectural drawing, {context}precise lines.",
            'seasonal': f"Moscow street view with modern residential buildings, {context}seasonal atmosphere, cinematic lighting.",
            'case': f"Interior of a modern Moscow apartment after renovation, {context}spacious living room, architectural transformation.",
            'offer': f"Professional architect meeting in a modern office, Moscow city view from window, {context}trust and expertise."
        }
        
        # Если в тексте есть специфические слова, добавляем их в промпт
        extra = ""
        if "кухня" in text.lower(): extra += "modern kitchen interior, "
        if "газ" in text.lower(): extra += "gas equipment safety, "
        if "санузел" in text.lower(): extra += "bathroom design, "
        
        prompt = prompts.get(post_type, f"Moscow real estate, {context}architectural detail, {extra}professional photography.")
        return base_style + prompt + f" Context: {text[:100]}"
    
    async def generate_image_async(self, prompt: str) -> Optional[str]:
        """
        Асинхронная версия генерации изображения
        """
        try:
            return await self.generator.generate_image_async(prompt)
        except Exception as e:
            logger.error(f"Error generating image (async): {e}")
            return None
