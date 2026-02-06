"""
Интеграция с Yandex Art API для генерации изображений
"""
import os
import aiohttp
import asyncio
import base64
from typing import Optional, Dict


class YandexArtClient:
    """Клиент для работы с Yandex Art API"""

    def __init__(self):
        self.api_key = os.getenv("YANDEX_API_KEY")
        self.folder_id = os.getenv("FOLDER_ID")
        self.endpoint = "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync"
        self.operation_endpoint = "https://llm.api.cloud.yandex.net/operations/"

        if not self.api_key or not self.folder_id:
            raise ValueError("YANDEX_API_KEY and FOLDER_ID must be set in environment")

    async def generate_image(self, prompt: str) -> Optional[bytes]:
        """
        Генерация изображения по текстовому промпту

        Args:
            prompt: Описание изображения

        Returns:
            bytes: Бинарные данные изображения или None при ошибке
        """
        # Модифицируем промпт согласно ТЗ: запрет на текст и aspect ratio 1:1 (уже в параметрах)
        final_prompt = f"{prompt}, professional digital art, highly detailed, no text, no letters, no words"

        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "modelUri": f"art://{self.folder_id}/yandex-art/latest",
            "generationOptions": {
                "seed": 42,
                "aspectRatio": {
                    "widthRatio": 1,
                    "heightRatio": 1
                }
            },
            "messages": [
                {
                    "weight": 1,
                    "text": final_prompt
                }
            ]
        }

        async with aiohttp.ClientSession() as session:
            try:
                # 1. Отправка запроса на генерацию
                async with session.post(self.endpoint, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"❌ Yandex Art Error (Post): {response.status} - {error_text}")
                        return None

                    result = await response.json()
                    operation_id = result.get("id")

                # 2. Ожидание выполнения (Polling)
                max_retries = 30
                for _ in range(max_retries):
                    await asyncio.sleep(2)
                    async with session.get(f"{self.operation_endpoint}{operation_id}", headers=headers) as op_resp:
                        if op_resp.status != 200:
                            continue

                        op_result = await op_resp.json()
                        if op_result.get("done"):
                            # Получаем изображение
                            image_base64 = op_result.get("response", {}).get("image")
                            if image_base64:
                                return base64.b64decode(image_base64)
                            return None

                print("❌ Yandex Art Error: Timeout")
                return None

            except Exception as e:
                print(f"❌ Yandex Art Exception: {e}")
                return None


yandex_art = YandexArtClient()
