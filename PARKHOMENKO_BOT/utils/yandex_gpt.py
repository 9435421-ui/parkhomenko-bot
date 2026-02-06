"""
Интеграция с YandexGPT API
"""
import os
import aiohttp
from typing import Optional, List, Dict


class YandexGPTClient:
    """Клиент для работы с YandexGPT API"""

    def __init__(self):
        self.api_key = os.getenv("YANDEX_API_KEY")
        self.folder_id = os.getenv("FOLDER_ID")
        self.endpoint = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        self.max_prompt_length = 3000  # Максимальная длина промпта в символах

        if not self.api_key or not self.folder_id:
            raise ValueError("YANDEX_API_KEY and FOLDER_ID must be set in environment")

    async def generate_response(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 400,
        model: str = "yandexgpt"
    ) -> str:
        """
        Генерация ответа от YandexGPT
        """
        # Проверка длины промпта
        prompt_length = len(user_prompt) + (len(system_prompt) if system_prompt else 0)
        if prompt_length > self.max_prompt_length:
            return "Извините, запрос слишком большой. Пожалуйста, сформулируйте вопрос короче."

        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "text": system_prompt})

        messages.append({"role": "user", "text": user_prompt})

        payload = {
            "modelUri": f"gpt://{self.folder_id}/{model}/latest",
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": max_tokens
            },
            "messages": messages
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result["result"]["alternatives"][0]["message"]["text"]
                    else:
                        error_text = await response.text()
                        return f"Ошибка API YandexGPT: {response.status}"
        except Exception as e:
            return f"Ошибка подключения к YandexGPT: {str(e)}"

    def _build_consultant_system_prompt(self) -> str:
        """Формирует системный промпт для ИИ-консультанта Антона ТЕРИОН"""
        return """
Ты — Антон, ИИ-ассистент компании ТЕРИОН по согласованию перепланировок.

ЖЕЛЕЗНЫЕ ПРАВИЛА:
1. Лимит: 250-350 символов (2-3 предложения max)
2. УПОМИНАЙ КОМПАНИЮ: в каждом 2-3 ответе говори "наша команда", "эксперты ТЕРИОН"
3. СТОИМОСТЬ: НИКОГДА не называй конкретные суммы. Предложи обсудить стоимость со специалистом.
4. ТВОЯ РОЛЬ: Помогать клиентам компании ТЕРИОН.
""".strip()

# Singleton instance
yandex_gpt = YandexGPTClient()
