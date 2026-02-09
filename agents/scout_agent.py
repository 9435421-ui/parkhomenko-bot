"""
Scout Agent — поиск трендовых тем для контента.
Специализация: Согласование перепланировок и переустройства помещений.
"""
import os
import logging
from typing import List, Dict
from datetime import datetime
from utils.knowledge_base import KnowledgeBase
from utils import router_ai, yandex_gpt

logger = logging.getLogger(__name__)


class ScoutAgent:
    """Агент для поиска трендовых тем и трендсеттинга"""
    
    def __init__(self):
        self.router_api_key = os.getenv("ROUTER_AI_KEY") or os.getenv("YANDEX_API_KEY")
        self.use_router = bool(self.router_api_key)
        self.kb = KnowledgeBase()
    
    async def scout_topics(self, count: int = 3) -> List[Dict]:
        """
        Ищет трендовые темы для контента о согласовании перепланировок.
        
        Returns:
            List[Dict] - список тем с описанием
        """
        logger.info("🔍 ScoutAgent: поиск трендовых тем...")
        
        topics = []
        
        # Тема 1: Изменения в Жилищном кодексе РФ 2026
        topic1 = await self._research_topic(
            "изменения в Жилищном кодексе РФ 2026, перепланировки"
        )
        topics.append(topic1)
        
        # Тема 2: Новые требования Мосжилинспекции
        topic2 = await self._research_topic(
            "новые требования Мосжилинспекции 2026, штрафы"
        )
        topics.append(topic2)
        
        # Тема 3: Кейсы узаконивания
        topic3 = await self._research_topic(
            "как узаконить перепланировку, которую невозможно согласовать"
        )
        topics.append(topic3)
        
        return topics
    
    async def _research_topic(self, query: str) -> Dict:
        """Исследует конкретную тему"""
        # Проверяем базу знаний
        kb_context = ""
        try:
            chunks = await self.kb.get_context(query, max_chunks=3)
            if chunks:
                kb_context = chunks[:500] if isinstance(chunks, str) else ""
        except Exception as e:
            logger.warning(f"KnowledgeBase error: {e}")
        
        # Генерируем тему через ИИ
        try:
            system_prompt = """Ты — эксперт по трендам в нише согласования перепланировок.
Твоя задача — предложить 1 цепляющую тему для поста в социальных сетях.

Требования:
- Тема должна быть актуальна на {date}
- Связана с законодательством РФ или практикой согласования
- Содержит проблема + решение
- Вызывает эмоции (страх штрафов, желание решить проблему)

Формат ответа:
1. Тема (коротко, цепляюще)
2. Почему это важно сейчас (1-2 предложения)
3. Ключевой инсайт (1 предложение)"""

            user_prompt = f"""Исследуй тему: {query}

База знаний:
{kb_context[:1000] if kb_context else 'Нет данных в базе'}

Предложи 1 конкретную тему для поста."""

            if self.use_router:
                response = await router_ai.generate_response(
                    user_prompt=user_prompt,
                    system_prompt=system_prompt.format(date=datetime.now().strftime("%B %Y")),
                    max_tokens=500
                )
                if response:
                    return self._parse_response(response, query)
            
            response = await yandex_gpt.generate_response(
                user_prompt=user_prompt,
                system_prompt=system_prompt.format(date=datetime.now().strftime("%B %Y")),
                max_tokens=500
            )
            if response:
                return self._parse_response(response, query)
                
        except Exception as e:
            logger.error(f"Scout AI error: {e}")
        
        # Fallback — возвращаем шаблонную тему
        return {
            "query": query,
            "title": f"Как согласовать {query} в 2026 году",
            "why": "Изменения в законодательстве делают это актуальным",
            "insight": "Специалисты знают нюансы, которые спасут от штрафов",
            "source": "template"
        }
    
    def _parse_response(self, response: str, query: str) -> Dict:
        """Парсит ответ ИИ"""
        lines = [l.strip() for l in response.strip().split('\n') if l.strip()]
        
        return {
            "query": query,
            "title": lines[0] if lines else f"Тема: {query}",
            "why": lines[1] if len(lines) > 1 else "",
            "insight": lines[2] if len(lines) > 2 else "",
            "source": "ai"
        }
    
    async def generate_content_ideas(self, niche: str = "перепланировки") -> List[str]:
        """Генерирует идеи для контента"""
        ideas = [
            "Почему дизайнер может подставить вас на 500 000 ₽ штрафа",
            "Объединение лоджии в 2026 году: мифы и реальность",
            "Как перенос мокрой зоны убивает стоимость квартиры",
            "Что будет, если не узаконить перепланировку перед продажей",
            "5 признаков того, что вашу перепланировку не согласуют",
        ]
        return ideas


# Singleton
scout_agent = ScoutAgent()


async def scout_content_ideas(count: int = 3) -> List[Dict]:
    """Удобная функция для поиска тем"""
    return await scout_agent.scout_topics(count)


if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("🧪 Тест Scout Agent\n")
        
        topics = await scout_content_ideas(3)
        
        for i, topic in enumerate(topics, 1):
            print(f"📌 Тема {i}: {topic['title']}")
            print(f"   Почему: {topic['why']}")
            print(f"   Инсайт: {topic['insight']}")
            print(f"   Источник: {topic['source']}\n")
        
        print("\n💡 Идеи для контента:")
        ideas = await scout_agent.generate_content_ideas()
        for i, idea in enumerate(ideas, 1):
            print(f"  {i}. {idea}")
    
    asyncio.run(test())
