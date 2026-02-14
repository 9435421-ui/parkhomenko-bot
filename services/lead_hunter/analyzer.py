import logging
from typing import Optional

logger = logging.getLogger(__name__)

class LeadAnalyzer:
    """AI-анализ постов на предмет 'горячих' лидов"""
    
    def __init__(self):
        pass
        
    async def analyze_post(self, text: str) -> float:
        """
        Анализирует текст поста и возвращает оценку 'горячести' от 0 до 1.
        """
        logger.info("🧠 LeadAnalyzer: анализ поста...")
        # В будущем здесь будет AI-анализ через YandexGPT/RouterAI
        if "нужна помощь" in text.lower() or "как узаконить" in text.lower():
            return 0.9
        return 0.1
