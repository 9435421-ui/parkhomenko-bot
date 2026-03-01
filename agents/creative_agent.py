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
        """
        Ищет актуальные темы для контента на основе Жилищного кодекса и трендов
        
        Args:
            count: Количество тем для поиска
            
        Returns:
            Список словарей с полями 'title' и 'insight'
        """
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
            
            # Извлекаем JSON из ответа
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                topics = json.loads(match.group(0))
                return topics[:count]
            
            logger.error(f"Не удалось распарсить JSON из ответа YandexGPT: {response}")
            return []
            
        except Exception as e:
            logger.error(f"Ошибка при скаутинге тем в CreativeAgent: {e}")
            return []


# Создаем экземпляр для импорта
creative_agent = CreativeAgent()
