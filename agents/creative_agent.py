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

# --- ИСПРАВЛЕНИЕ: Адаптивный стиль без упоминаний "High-end" и особняков ---
STYLE_PRESET = (
    "Realistic interior or technical floor plan matching the text. "
    "The image must EXACTLY match the post topic and content. "
    "For mass housing topics (ЖК, хрущевка, ПИК, Самолет): show typical apartment layouts, "
    "realistic renovation examples, or technical floor plans. "
    "For technical topics: show diagrams, floor plans, or construction details. "
    "For general topics: show relevant interior spaces or architectural solutions. "
    "No abstract elements, no luxury bias, no mansions unless specifically required by the topic. "
    "Focal point on spatial solutions and practical examples. No people, no text on image."
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
        
        # Fallback на Router AI, если Yandex не сработал
        if self.use_router:
            try:
                response = await router_ai.generate_response(
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                    max_tokens=1000
                )
                if response:
                    return self._parse_response(response, query)
            except Exception as e:
                logger.warning(f"Router AI error: {e}")
            
        return {
            "query": query,
            "title": f"Важное о {query}",
            "body": "Текст генерируется...",
            "cta": f"Пройдите квиз: {self.quiz_link}",
            "source": "template"
        }
    
    def _parse_response(self, response: str, query: str) -> Dict:
        """Парсит ответ ИИ и извлекает структурированные данные поста"""
        if not response:
            return {
                "query": query,
                "title": f"Важное о {query}",
                "body": "Текст генерируется...",
                "cta": f"Пройдите квиз: {self.quiz_link}",
                "source": "template"
            }
        
        # Извлекаем текст ответа
        text = response.strip()
        
        # Разбиваем на строки
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        # Первая строка — заголовок
        title = lines[0] if lines else f"Важное о {query}"
        # Убираем нумерацию и кавычки из заголовка
        title = re.sub(r'^\d+\.\s*', '', title)
        title = re.sub(r'^["«](.*)["»]$', r'\1', title)
        title = title.strip()
        
        # Остальные строки — тело поста
        body_lines = lines[1:] if len(lines) > 1 else []
        body = "\n\n".join(body_lines) if body_lines else text
        
        # Проверяем, есть ли уже ссылка на квиз в тексте
        has_quiz = self.quiz_link in body or "квиз" in body.lower()
        
        # Формируем CTA
        if has_quiz:
            cta = ""
        else:
            cta = f"🧐 Узнайте стоимость вашей перепланировки за 1 минуту:\n👉 {self.quiz_link}"
        
        return {
            "query": query,
            "title": title,
            "body": body,
            "cta": cta,
            "source": "ai"
        }

# Создаем экземпляр агента для использования в других файлах
creative_agent = CreativeAgent()