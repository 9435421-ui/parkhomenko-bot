import os
import openai
from typing import Optional, Dict

class ContentGenerator:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        self.model = "openai/gpt-4o-mini"
        self.client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
        )

    async def generate_post_text(self, theme: str, post_type: str) -> str:
        """Генерирует текст поста с учетом ToV ТОРИОН"""
        prompt = f"""
        Ты — экспертный копирайтер бренда «ТОРИОН» (эксперты по перепланировкам).
        Напиши пост на тему: {theme}
        Тип поста: {post_type}

        Требования:
        1. Стиль: экспертный, но доступный, без использования конкретных имен (только «наши эксперты», «специалисты ТОРИОН»).
        2. Структура: цепляющий заголовок, основная часть с пользой, четкий призыв к действию (CTA).
        3. CTA должен вести в бота @TorionProjectBot.
        4. Добавь в конце дисклеймер: «Информация носит ознакомительный характер и не является публичной офертой».
        5. Не используй личные местоимения «я», только «мы» или безличные формы.
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

    async def generate_image_prompt(self, post_text: str) -> str:
        """Генерирует промпт для Yandex Art на основе текста поста"""
        prompt = f"""
        На основе текста поста ниже, создай короткий промпт для генерации изображения в Yandex Art.
        Изображение должно быть в стиле современного интерьера, без людей, уютное и профессиональное.
        Текст поста: {post_text[:500]}

        Формат ответа: только текст промпта на русском языке.
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content

# Singleton
generator = ContentGenerator()
