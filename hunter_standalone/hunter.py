"""
LeadHunter - AI-агент для анализа и скоринга лидов
Анализирует сообщения и определяет их "горячесть" и приоритет
"""
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class LeadHunter:
    """Класс для анализа лидов через AI"""
    
    def __init__(self, db):
        """
        Инициализация LeadHunter
        
        Args:
            db: Экземпляр HunterDatabase для доступа к базе данных
        """
        self.db = db
    
    async def hunt(self, messages: List[Dict]) -> List[Dict]:
        """
        Анализирует список сообщений и возвращает скоринг лидов
        
        Args:
            messages: Список словарей с полями:
                - text: Текст сообщения
                - url: URL поста
        
        Returns:
            Список словарей с результатами анализа:
                - url: URL поста
                - content: Текст сообщения
                - hotness: Уровень "горячести" (0-5, где 3+ считается горячим)
                - intent: Намерение клиента
                - pain_stage: Стадия боли (ST-1, ST-2, ST-3, ST-4)
                - priority_score: Приоритетный балл (0-10)
        
        Note:
            В текущей версии это заглушка, которая возвращает базовый анализ.
            В будущем здесь будет интеграция с AI-моделью (Yandex GPT, Router AI)
            для реального анализа намерений и определения приоритета.
        """
        analyzed_leads = []
        
        for msg in messages:
            text = msg.get("text", "") or ""
            url = msg.get("url", "") or ""
            
            if not text:
                continue
            
            # Базовый анализ (заглушка)
            # В будущем здесь будет вызов AI для реального анализа
            text_lower = text.lower()
            
            # Простая эвристика для определения "горячести"
            hotness = 3  # Средний уровень по умолчанию
            
            # Ключевые слова для повышения приоритета
            hot_keywords = [
                "срочно", "нужно", "помогите", "проблема", "не могу",
                "не получается", "отказали", "не знаю что делать",
                "перепланировка", "согласование", "легализация"
            ]
            
            if any(keyword in text_lower for keyword in hot_keywords):
                hotness = 4
            
            # Определение стадии боли (упрощенная логика)
            pain_stage = "ST-2"  # Планирование по умолчанию
            
            if any(word in text_lower for word in ["срочно", "критично", "проблема"]):
                pain_stage = "ST-3"  # Активная боль
            elif any(word in text_lower for word in ["интерес", "узнать", "информация"]):
                pain_stage = "ST-1"  # Интерес
            
            # Приоритетный балл (0-10)
            priority_score = 5  # Средний приоритет
            
            if hotness >= 4:
                priority_score = 7
            if pain_stage in ("ST-3", "ST-4"):
                priority_score = 8
            
            lead_analysis = {
                "url": url,
                "content": text[:2000],  # Ограничение длины
                "hotness": hotness,
                "intent": "inquiry",  # Базовое намерение
                "pain_stage": pain_stage,
                "priority_score": priority_score
            }
            
            analyzed_leads.append(lead_analysis)
        
        logger.info(f"✅ Проанализировано {len(analyzed_leads)} лидов")
        return analyzed_leads
