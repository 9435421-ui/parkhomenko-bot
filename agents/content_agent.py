import requests
import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class ContentAgent:
    def __init__(self):
        self.folder_id = os.getenv("FOLDER_ID")
        self.api_key = os.getenv("YANDEX_API_KEY")
        self.endpoint = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        self.brief_content = self._load_brief()

    def _load_brief(self):
        """Загружает базу знаний"""
        paths = ["BRIEF_pereplanirovki.md", "docs/09_ИИ_консультант/Промпт_ИИ_консультанта.md"]
        for path in paths:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception as e:
                    logger.error(f"Error loading brief from {path}: {e}")
        return "База знаний не найдена. Используйте общие знания по перепланировкам в Москве."

    async def generate_post(self, topic: str) -> str:
        """Генерирует текст поста через YandexGPT"""
        system_prompt = f"""
Ты — экспертный контент-менеджер компании TERION (ИП Пархоменко). 
Твоя задача: написать пост для Telegram-канала о перепланировках в Москве.

Тема: {topic}

Стиль: Профессиональный, но доступный. Экспертный, вызывающий доверие.
База знаний:
{self.brief_content[:2000]}

Требования:
1. Текст должен быть структурированным (используй абзацы).
2. Используй эмодзи умеренно.
3. В конце обязательно добавь призыв к действию (CTA).
4. Не используй сложные юридические термины без объяснения.
"""
        user_prompt = f"Напиши экспертный пост на тему: {topic}"

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Api-Key {self.api_key}",
                "x-folder-id": self.folder_id
            }

            payload = {
                "modelUri": f"gpt://{self.folder_id}/yandexgpt/latest",
                "completionOptions": {
                    "stream": False,
                    "temperature": 0.6,
                    "maxTokens": 1500
                },
                "messages": [
                    {"role": "system", "text": system_prompt},
                    {"role": "user", "text": user_prompt}
                ]
            }

            # Используем requests для простоты, так как это агент
            response = requests.post(self.endpoint, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result['result']['alternatives'][0]['message']['text']
        except Exception as e:
            logger.error(f"Error generating post: {e}")
            return f"Ошибка при генерации поста на тему '{topic}'. Пожалуйста, попробуйте позже."
