import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict
from utils.yandex_gpt import YandexGPT
from utils.knowledge_base import knowledge_base

logger = logging.getLogger(__name__)

class ContentAgent:
    """Агент TERION для генерации экспертного контента по перепланировкам"""

    def __init__(self):
        self.ai = YandexGPT()
        # Темы для автоплана, специфичные для ТЕРИОН
        self.expert_topics = [
            "Законодательство: Новые правила согласования в 2026 году",
            "Инвестиции: Как деление на студии увеличивает капитализацию",
            "Кейс: Узаконивание сложной перепланировки в Москве",
            "БТИ: Почему техпаспорт — это еще не всё",
            "Безопасность: Какие стены нельзя трогать ни при каких условиях",
            "Экономика: Сколько стоит ошибка в согласовании",
            "Совет эксперта: Как выбрать квартиру под инвест-проект"
        ]

    async def generate_week_plan(self) -> List[Dict]:
        """Генерирует план постов на 7 дней"""
        plan = []
        today = datetime.now()

        for i, topic in enumerate(self.expert_topics):
            publish_date = today + timedelta(days=i)

            # Получаем контекст из нашей базы знаний для точности
            context = await knowledge_base.get_context(topic)

            prompt = f"""
            Ты — Антон, ИИ-помощник Юлии Пархоменко в компании TERION.
            Твоя задача: написать экспертный пост для Telegram на тему: {topic}

            ИСПОЛЬЗУЙ ДАННЫЕ ИЗ БАЗЫ ЗНАНИЙ:
            {context}

            ТРЕБОВАНИЯ К ПОСТУ:
            1. Стиль: Профессиональный, но доступный.
            2. Обязательно упомяни, что финальное решение за экспертом Юлией Пархоменко.
            3. В конце добавь призыв пройти наш квиз в боте.
            4. Тон: Технологичный (мы используем ИИ для расчетов).
            """

            content = await self.ai.generate_response(prompt)

            # Формируем структуру поста
            post = {
                "day": i + 1,
                "date": publish_date.strftime("%d.%m.%Y"),
                "topic": topic,
                "text": content,
                "image_prompt": f"Modern luxury apartment interior, architectural blueprint overlay, professional lighting, 8k, style of TERION agency, focus on {topic}"
            }
            plan.append(post)

        return plan

async def create_cover_data(self, title: str):
        """
        Подготовка данных для наложения текста на обложку
        (Логика для Pillow будет в image_agent)
        """
        return {
            "text": title.upper(),
            "font_color": "#FFFFFF",
            "bg_overlay": "rgba(0, 0, 139, 0.5)", # Фирменный синий TERION
            "logo": "terion_logo.png"
        }

    async def create_posts_from_interview(self, voice_text: str) -> Dict:
        """
        Создание постов из голосового сообщения Юлии

        Args:
            voice_text: Текст из голосового сообщения

        Returns:
            Dict: Словарь с вариантами постов и рекомендацией канала
        """
        # Анализируем содержание для определения канала
        target_channel = self._determine_target_channel(voice_text)

        # Генерируем пост для выбранного канала
        post_text = await self._generate_post_for_channel(voice_text, target_channel)

        return {
            "text": post_text,
            "target_channel": target_channel,
            "voice_text": voice_text
        }

    def _determine_target_channel(self, text: str) -> str:
        """
        Определение канала для публикации на основе содержания

        Args:
            text: Текст для анализа

        Returns:
            str: Рекомендованный канал ("TERION" или "Дом Гранд")
        """
        text_lower = text.lower()

        # Ключевые слова для Дом Гранд (инвестиции, студии, доход)
        dom_grand_keywords = [
            "студия", "инвестиция", "доход", "аренда",
            "капитализация", "прибыль", "финансы",
            "рынок", "цены", "недвижимость"
        ]

        # Ключевые слова для TERION (БТИ, законы, согласование)
        terion_keywords = [
            "бти", "техпаспорт", "согласование",
            "закон", "норматив", "перепланировка",
            "архитектура", "проект", "документ"
        ]

        # Проверяем наличие ключевых слов
        dom_grand_count = sum(1 for kw in dom_grand_keywords if kw in text_lower)
        terion_count = sum(1 for kw in terion_keywords if kw in text_lower)

        # Принимаем решение на основе количества ключевых слов
        if dom_grand_count > terion_count:
            return "Дом Гранд"
        elif terion_count > dom_grand_count:
            return "TERION"
        else:
            # Если ключевых слов поровну или нет явных ключевых слов
            # Приоритет отдаем TERION (основной бизнес)
            return "TERION"

    async def _generate_post_for_channel(self, text: str, channel: str) -> str:
        """
        Генерация поста для конкретного канала

        Args:
            text: Исходный текст
            channel: Целевой канал

        Returns:
            str: Сгенерированный пост
        """
        # Получаем контекст из базы знаний
        context = await knowledge_base.get_context(text)

        # Формируем промпт в зависимости от канала
        if channel == "Дом Гранд":
            prompt = f"""
            Ты — Антон, ИИ-помощник Юлии Пархоменко в компании TERION.
            Твоя задача: написать экспертный пост для канала "Дом Гранд" на основе голосового сообщения:

            ИСХОДНОЕ СООБЩЕНИЕ:
            {text}

            ИСПОЛЬЗУЙ ДАННЫЕ ИЗ БАЗЫ ЗНАНИЙ:
            {context}

            ТРЕБОВАНИЯ К ПОСТУ:
            1. Стиль: Инвестиционный, ориентированный на доход и капитализацию.
            2. Цветовая гамма: Золотисто-бежевая (для обложек).
            3. Целевая аудитория: Инвесторы, собственники жилья.
            4. Акцент: На финансовые выгоды и возможности.
            5. В конце добавь призыв к действию для инвесторов.
            """
        else:  # TERION
            prompt = f"""
            Ты — Антон, ИИ-помощник Юлии Пархоменко в компании TERION.
            Твоя задача: написать экспертный пост для канала "TERION" на основе голосового сообщения:

            ИСХОДНОЕ СООБЩЕНИЕ:
            {text}

            ИСПОЛЬЗУЙ ДАННЫЕ ИЗ БАЗЫ ЗНАНИЙ:
            {context}

            ТРЕБОВАНИЯ К ПОСТУ:
            1. Стиль: Профессиональный, технический.
            2. Цветовая гамма: Фирменный синий TERION с платиной (для обложек).
            3. Целевая аудитория: Клиенты, нуждающиеся в согласовании перепланировок.
            4. Акцент: На юридические аспекты и технические решения.
            5. В конце добавь призыв к действию для консультации.
            """

        # Генерируем контент
        content = await self.ai.generate_response(prompt)

        return content

async def create_cover_data(self, title: str):
        """
        Подготовка данных для наложения текста на обложку
        (Логика для Pillow будет в image_agent)
        """
        return {
            "text": title.upper(),
            "font_color": "#FFFFFF",
            "bg_overlay": "rgba(0, 0, 139, 0.5)", # Фирменный синий TERION
            "logo": "terion_logo.png"
        }

# Глобальный экземпляр
content_agent = ContentAgent()
