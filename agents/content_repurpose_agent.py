"""
Content Repurposing Agent - адаптация контента под разные форматы.
"""
import os
import logging
from typing import Dict, List
from utils import router_ai, yandex_gpt

logger = logging.getLogger(__name__)


class ContentRepurposingAgent:
    """Агент для ресайклинга контента"""
    
    def __init__(self):
        self.router_api_key = os.getenv("ROUTER_AI_KEY") or os.getenv("YANDEX_API_KEY")
        self.use_router = bool(self.router_api_key)
    
    async def repurpose(self, content: str, target_format: str) -> Dict:
        """Адаптирует контент"""
        formats = {
            'tg_post': {'max': 4000, 'style': 'эмодзи, хук, CTA'},
            'vk_post': {'max': 15000, 'style': 'нейтральный'},
            'brief': {'max': 500, 'style': 'краткий'},
        }
        spec = formats.get(target_format, formats['tg_post'])
        
        system_prompt = f"""Адаптируй контент под {target_format}.
Стиль: {spec['style']}. Сохрани смысл."""
        
        try:
            if self.use_router:
                result = await router_ai.generate(system_prompt, content)
                if result:
                    return {'text': result, 'platform': target_format}
            
            result = await yandex_gpt.generate(system_prompt, content)
            return {'text': result or content, 'platform': target_format}
        except Exception as e:
            logger.error(f"Error: {e}")
            return {'text': content, 'platform': target_format}
    
    async def extract_key_points(self, content: str) -> List[str]:
        """Извлекает ключевые пункты"""
        prompt = "Извлеки 3-5 ключевых пунктов из текста:"
        
        try:
            if self.use_router:
                result = await router_ai.generate(prompt, content)
                if result:
                    return [p.strip() for p in result.split('\n') if p.strip()]
            result = await yandex_gpt.generate(prompt, content)
            if result:
                return [p.strip() for p in result.split('\n') if p.strip()]
        except Exception as e:
            logger.error(f"Ошибка извлечения ключевых пунктов: {e}")
        return []
    
    async def generate_hashtags(self, content: str, count: int = 10) -> List[str]:
        """Генерирует хештеги"""
        prompt = f"Сгенерируй {count} релевантных хештегов для:"
        
        try:
            if self.use_router:
                result = await router_ai.generate(prompt, content)
                if result:
                    return [h.strip() for h in result.split() if h.strip().startswith('#')]
            result = await yandex_gpt.generate(prompt, content)
            if result:
                return [h.strip() for h in result.split() if h.strip().startswith('#')]
        except Exception as e:
            logger.error(f"Ошибка генерации хештегов: {e}")
        return []


content_repurpose_agent = ContentRepurposingAgent()


async def repurpose_content(content: str, target_format: str) -> Dict:
    return await content_repurpose_agent.repurpose(content, target_format)
