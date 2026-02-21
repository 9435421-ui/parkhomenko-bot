"""
Creative Agent — генерация идей контента и анализ трендов.
Специализация: Согласование перепланировок и переустройства помещений.
"""
import os
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime
from utils.knowledge_base import KnowledgeBase
from utils import router_ai, yandex_gpt

logger = logging.getLogger(__name__)

# --- ИСПРАВЛЕНИЕ: Адаптивный стиль вместо жесткого "High-end" ---
STYLE_PRESET = (
    "Architectural minimalism, clean professional lines. "
    "MATCH THE SETTING: If the topic is about budget/mass housing (ЖК, хрущевка), "
    "show realistic modern renovation or technical drawings. "
    "If the topic is about luxury/houses, show premium interiors. "
    "Focal point on spatial solutions and floor plans. No people, no text on image."
)

class CreativeAgent:
    """Агент для поиска трендовых тем и трендсеттинга"""
    
    def __init__(self):
        # Приоритет Yandex для РФ, так как он лучше знает наши законы
        self.yandex_key = os.getenv("YANDEX_API_KEY")
        self.router_api_key = os.getenv("ROUTER_AI_KEY")
        self.use_router = bool(self.router_api_key)
        self.kb = KnowledgeBase()
        # Ссылка на квиз из конфига
        self.quiz_link = os.getenv("VK_QUIZ_LINK", "https://t.me/Parkhovenko_i_kompaniya_bot?start=quiz")
    
    async def scout_topics(self, count: int = 3) -> List[Dict]:
        """Ищет трендовые темы (добавлен фокус на массовый сегмент)"""
        logger.info("🔍 CreativeAgent: поиск трендовых тем (Массовый сегмент + ГОСТ)...")
        
        topics = []
        # Тема 1: Массовая застройка (ПИК/Самолет)
        topic1 = await self._research_topic("перепланировка в новостройках ПИК и Самолет 2026, особенности")
        topics.append(topic1)
        
        # Тема 2: Технические нюансы (Подоконные блоки/Мокрые зоны)
        topic2 = await self._research_topic("демонтаж подоконного блока и объединение лоджии: новые правила 2026")
        topics.append(topic2)
        
        # Тема 3: Юридическая база
        topic3 = await self._research_topic("предписания Мосжилинспекции и как их избежать")
        topics.append(topic3)
        
        return topics

    async def _research_topic(self, query: str) -> Dict:
        """Исследует тему и формирует ТЗ для поста с ФУТЕРОМ"""
        kb_context = ""
        try:
            chunks = await self.kb.get_context(query, max_chunks=3)
            if chunks:
                kb_context = chunks[:500] if isinstance(chunks, str) else ""
        except Exception as e:
            logger.warning(f"KnowledgeBase error: {e}")

        # --- ИСПРАВЛЕНИЕ: Жесткое требование к КВИЗУ и ХЭШТЕГАМ в системном промпте ---
        system_prompt = f"""Ты — эксперт TERION по согласованию перепланировок.
Твоя задача — создать пост, который продает экспертность Юлии Владимировны Пархоменко.

ОБЯЗАТЕЛЬНАЯ СТРУКТУРА:
1. Заголовок (без кавычек и цифр)
2. Проблема и решение (коротко, экспертно)
3. ИНСАЙТ
4. ФУТЕР (Призыв к действию):
🧐 Узнайте стоимость вашей перепланировки за 1 минуту:
👉 {self.quiz_link}

#перепланировка #МЖИ #БТИ #TERION #согласование #Москва #МО"""

        user_prompt = f"""Тема: {query}\nКонтекст: {kb_context}\nСоздай экспертный пост."""

        # Логика генерации (Yandex -> Router) остается прежней, но теперь с новым промптом
        try:
            response = await yandex_gpt.generate_response(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=1000
            )
            if response:
                return self._parse_response(response, query)
        except Exception as e:
            logger.warning(f"YandexGPT error: {e}")
            # Fallback на Router AI...
            
        return {
            "query": query,
            "title": f"Важное о {query}",
            "body": "Текст генерируется...",
            "cta": f"Пройдите квиз: {self.quiz_link}",
            "source": "template"
        }

    # ... (остальные методы парсинга оставляем без изменений) ...