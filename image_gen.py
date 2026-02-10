"""
Модуль генерации изображений через Router AI (Flux).

Используется для создания визуальных материалов для постов
в Telegram-каналах ТЕРИОН и ДОМ ГРАНД.

Модель: Flux (через Router AI)
"""
import os
import logging
import aiohttp
from typing import Optional

logger = logging.getLogger(__name__)


async def generate(prompt: str) -> Optional[str]:
    """
    Генерирует изображение по текстовому промпту через Router AI (Flux).

    Args:
        prompt: Текстовое описание желаемого изображения

    Returns:
        URL изображения или None в случае ошибки
    """
    ENABLE_IMAGE_GEN = os.getenv("ENABLE_IMAGE_GENERATION", "false").lower() == "true"
    ROUTER_AI_IMAGE_KEY = os.getenv("ROUTER_AI_IMAGE_KEY", "").strip()
    FLUX_MODEL = os.getenv("FLUX_MODEL", "flux-1-dev")

    if not ENABLE_IMAGE_GEN:
        logger.info("Генерация изображений отключена (ENABLE_IMAGE_GENERATION=false)")
        return None

    if not ROUTER_AI_IMAGE_KEY:
        logger.error("ROUTER_AI_IMAGE_KEY не настроен в переменных окружения")
        return None

    # API Router AI для генерации изображений
    url = os.getenv("ROUTER_IMAGE_URL", "https://api.router.ai/v1/image_generation")

    headers = {
        "Authorization": f"Bearer {ROUTER_AI_IMAGE_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": FLUX_MODEL,
        "prompt": prompt,
        "width": 1024,
        "height": 1024,
        "num_images": 1
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as response:
                if response.status != 200:
                    logger.error(f"Image API error: {response.status}")
                    return None
                
                result = await response.json()

                # Получаем URL изображения
                if result.get("data") and len(result["data"]) > 0:
                    image_url = result["data"][0].get("url") or result["data"][0].get("image_url")
                    if image_url:
                        logger.info(f"Изображение успешно сгенерировано: {image_url}")
                        return image_url

                logger.warning(f"Не удалось получить URL изображения: {result}")
                return None

    except aiohttp.ClientError as e:
        logger.error(f"aiohttp error при генерации изображения: {e}")
        return None
    except Exception as e:
        logger.error(f"Ошибка генерации изображения: {e}")
        return None
