import requests
import os
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

class ContentAgent:
    def __init__(self):
        from utils.yandex_gpt import yandex_gpt
        self.gpt = yandex_gpt
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
""".strip()

        try:
            result = await self.gpt.generate_response(
                user_prompt=f"Напиши экспертный пост на тему: {topic}",
                system_prompt=system_prompt,
                temperature=0.6,
                max_tokens=1500
            )
            return result
        except Exception as e:
            logger.error(f"Error generating post: {e}")
            return f"Ошибка при генерации поста на тему '{topic}'. Пожалуйста, попробуйте позже."
