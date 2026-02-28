import os
import logging

# Настройка логирования для модуля
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImageAgent:
    def __init__(self, api_key: str | None = None, folder_id: str | None = None):
        """
        Инициализация ImageAgent
        
        Args:
            api_key: API ключ Yandex Cloud (если None, берется из .env)
            folder_id: ID каталога Yandex Cloud (если None, берется из .env)
        """
        self.api_key = api_key or os.getenv("YANDEX_API_KEY")
        self.folder_id = folder_id or os.getenv("FOLDER_ID")
        logger.info("ImageAgent инициализирован (режим заглушки)")

    def build_image_prompt(self, post_type: str, text: str) -> str:
        """
        Формирует текстовое описание (промпт) для генерации картинки
        на основе типа поста и его содержания.
        """
        base_style = "Photorealistic, professional architectural photography, high quality, 4k. "

        prompts = {
            'news': f"Modern office building with blueprints, legal documents, urban style. {text[:50]}",
            'fact': f"Educational concept, light bulb, building plan, magnifying glass over documents. {text[:50]}",
            'seasonal': f"House exterior during appropriate season, cozy lighting, real estate concept. {text[:50]}",
            'case': f"Before and after floor plan transformation, modern interior design, renovation process. {text[:50]}",
            'offer': f"Friendly architect consulting client, signing contract, keys to new property. {text[:50]}"
        }

        # Получаем промпт по типу или дефолтный
        prompt = prompts.get(post_type, f"Real estate redevelopment concept. {text[:50]}")
        return base_style + prompt

    def generate_image(self, prompt: str) -> str | None:
        """
        Заглушка для будущей генерации изображения.
        """
        logger.warning(f"Попытка генерации по промпту: {prompt}. Ошибка: API не настроен.")
        return None
