import os
import requests
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROUTER_AI_KEY = os.getenv("ROUTER_AI_KEY")
BASE_URL = "https://routerai.ru/api/v1"

TERION_PROMPT_PREFIX = (
    "Professional architectural 3D visualization of a modern apartment renovation, "
    "open space kitchen and living room, realistic lighting, high detail, "
    "minimalist style, 4k resolution, company style: TERION. "
)

def generate_image(prompt: str, model: str = "flux-1-dev") -> str | None:
    """
    Генерирует изображение через Router AI Image API.

    Args:
        prompt: Описание изображения
        model: Модель для генерации (по умолчанию flux-1-dev)

    Returns:
        URL сгенерированного изображения или None в случае ошибки
    """
    if not ROUTER_AI_KEY:
        logger.error("ROUTER_AI_KEY not found in environment variables")
        return None

    full_prompt = TERION_PROMPT_PREFIX + prompt

    headers = {
        "Authorization": f"Bearer {ROUTER_AI_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "prompt": full_prompt,
        "width": 1024,
        "height": 1024,
        "num_images": 1
    }

    try:
        # Предполагаемый эндпоинт для генерации изображений
        response = requests.post(f"{BASE_URL}/images/generations", json=payload, headers=headers, timeout=60)
        response.raise_for_status()

        result = response.json()
        # Предполагаемая структура ответа
        if "data" in result and len(result["data"]) > 0:
            return result["data"][0].get("url")
        elif "url" in result:
            return result["url"]

        logger.error(f"Unexpected response format from Router AI: {result}")
        return None

    except Exception as e:
        logger.error(f"Error generating image via Router AI: {e}")
        return None
