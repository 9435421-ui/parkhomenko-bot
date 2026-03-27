"""
CreativeAgent - агент для поиска актуальных тем для контента
"""
import logging
import json
import re
from typing import List, Dict, Optional
from utils.yandex_gpt import YandexGPTClient

logger = logging.getLogger(__name__)


class CreativeAgent:
    """Агент для скаутинга актуальных тем для контента"""
    
    def __init__(self):
        self.gpt = YandexGPTClient()

    async def scout_topics(self, count: int = 3) -> List[Dict[str, str]]:
        """Ищет актуальные темы для контента"""
        system_prompt = (
            "Ты — эксперт по перепланировкам и жилищному законодательству РФ. "
            "Твоя задача — предложить актуальные темы для постов в блог компании, которая занимается согласованием перепланировок. "
            "Темы должны основываться на последних изменениях в Жилищном кодексе РФ (2024-2025 гг) и частых болях клиентов. "
            "Отвечай строго в формате JSON: [{\"title\": \"...\", \"insight\": \"...\"}, ...]"
        )
        user_prompt = f"Подготовь список из {count}-х актуальных тем для постов на текущую неделю. Сделай акцент на изменениях в ЖК РФ и практических советах."
        try:
            response = await self.gpt.generate_response(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=1000
            )
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                topics = json.loads(match.group(0))
                return topics[:count]
            logger.error(f"Не удалось распарсить JSON: {response}")
            return []
        except Exception as e:
            logger.error(f"Ошибка scout_topics: {e}")
            return []

    async def generate_base_expert_pack(self, count: int = 9) -> List[Dict[str, str]]:
        """Генерирует базовый экспертный пакет (9 постов) из тем агента."""
        topics = await self.scout_topics(count=count)
        posts = []
        for t in topics:
            title = t.get("title", "Экспертный пост")
            base_body = t.get("insight", "") or f"Пост эксперта по теме: {title}."
            posts.append({
                "title": title,
                "body": base_body,
                "cta": "Запишитесь на консультацию по перепланировке", 
                "theme": "base_expert",
                "image_prompt": f"Экспертная обложка для темы: {title}"
            })
        return posts

    async def ideas_from_spy_leads(self, leads: list, count: int = 3, trends: list = None) -> List[Dict[str, str]]:
        """Генерирует идеи для контента на основе свежих лидов из шпиона"""
        if not leads:
            return await self.scout_topics(count=count)

        leads_text = "\n".join([
            f"- {l.get('text', '')[:200]}" for l in leads[:20] if l.get('text')
        ])
        trends_text = ""
        if trends:
            trends_text = "\nТренды недели: " + ", ".join([
                t.get('keyword', '') for t in trends[:10] if t.get('keyword')
            ])

        system_prompt = (
            "Ты — контент-стратег компании по согласованию перепланировок в Москве. "
            "На основе реальных вопросов и болей людей из соцсетей придумай идеи для постов. "
            "Каждая идея должна закрывать реальную боль клиента и вести к обращению в компанию. "
            "Отвечай строго в формате JSON: [{\"title\": \"...\", \"insight\": \"...\"}, ...]"
        )
        user_prompt = (
            f"Вот свежие обсуждения людей о перепланировках:\n{leads_text}\n{trends_text}\n\n"
            f"Придумай {count} идеи для постов. "
            "title — цепляющий заголовок поста, insight — почему эта тема сейчас актуальна и какую боль закрывает."
        )
        try:
            response = await self.gpt.generate_response(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=1000
            )
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                topics = json.loads(match.group(0))
                return topics[:count]
            logger.error(f"ideas_from_spy_leads: не удалось распарсить JSON: {response}")
            return await self.scout_topics(count=count)
        except Exception as e:
            logger.error(f"ideas_from_spy_leads error: {e}")
            return await self.scout_topics(count=count)


# Создаем экземпляр для импорта
creative_agent = CreativeAgent()
