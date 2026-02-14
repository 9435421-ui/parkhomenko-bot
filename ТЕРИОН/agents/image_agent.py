import os
import logging

ENABLE_IMG = os.getenv("ENABLE_IMAGE_GENERATION", "false").lower() == "true"

def generate_image(prompt: str) -> str | None:
    """
    Генерирует изображение по текстовому промпту.

    Args:
        prompt: Текстовый промпт для генератора изображений

    Returns:
        URL или путь к сгенерированному изображению, или None если генерация отключена
    """
    if not ENABLE_IMG:
        return None

    # TODO: Implement actual image generation logic here
    # For now, return None to indicate no image generated
    return None
