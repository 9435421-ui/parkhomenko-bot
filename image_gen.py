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
    from config import ENABLE_IMAGE_GENERATION as ENABLE_IMAGE_GEN
    ROUTER_AI_IMAGE_KEY = (os.getenv("ROUTER_AI_IMAGE_KEY") or os.getenv("ROUTER_AI_KEY") or "").strip()
    FLUX_MODEL = os.getenv("FLUX_MODEL", "flux-1-dev")

    if not ENABLE_IMAGE_GEN:
        logger.info("Генерация изображений отключена в конфиге")
        return None

    if not ROUTER_AI_IMAGE_KEY:
        logger.error("ROUTER_AI_IMAGE_KEY / ROUTER_AI_KEY не настроен")
        return None

    # API Router AI для генерации изображений (стандарт OpenAI)
    url = os.getenv("ROUTER_IMAGE_URL", "https://routerai.ru/api/v1/images/generations")

    headers = {
        "Authorization": f"Bearer {ROUTER_AI_IMAGE_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": FLUX_MODEL,
        "prompt": prompt,
        "size": "1024x1024",
        "n": 1
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
