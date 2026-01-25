import os
import logging

ENABLE_IMG = os.getenv("ENABLE_IMAGE_GENERATION", "false").lower() == "true"

import requests
import json
import time

def generate_image(prompt: str) -> str | None:
    """
    Генерирует изображение через Yandex Art API.

    Args:
        prompt: Текстовый промпт для генератора изображений

    Returns:
        URL или base64 данные изображения, или None если генерация не удалась
    """
    if not ENABLE_IMG:
        return None

    folder_id = os.getenv("FOLDER_ID")
    api_key = os.getenv("YANDEX_API_KEY")

    if not folder_id or not api_key:
        logging.error("FOLDER_ID or YANDEX_API_KEY not set for image generation")
        return None

    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync"

    headers = {
        "Authorization": f"Api-Key {api_key}",
        "Content-Type": "application/json"
    }

    data = {
        "modelUri": f"art://{folder_id}/yandex-art/latest",
        "generationOptions": {
            "seed": int(time.time())
        },
        "messages": [
            {
                "weight": 1,
                "text": prompt
            }
        ]
    }

    try:
        # 1. Запрос на генерацию (асинхронный)
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response.raise_for_status()
        operation = response.json()
        operation_id = operation.get("id")

        if not operation_id:
            return None

        # 2. Ожидание результата
        check_url = f"https://llm.api.cloud.yandex.net/operations/{operation_id}"
        for _ in range(10): # Ждем до 50 секунд
            time.sleep(5)
            check_response = requests.get(check_url, headers=headers, timeout=10)
            check_response.raise_for_status()
            result = check_response.json()

            if result.get("done"):
                # Изображение готово (в формате base64 в поле response -> image)
                image_base64 = result.get("response", {}).get("image")
                if image_base64:
                    # Возвращаем префикс для телеграма, чтобы он понял, что это файл
                    # В telebot можно передать байты
                    import base64
                    return base64.b64decode(image_base64)
                break

        return None

    except Exception as e:
        logging.error(f"Ошибка генерации изображения: {e}")
        return None
