import os
import re
import json
import asyncio
from typing import List, Dict, Optional
from .database import HunterDatabase

try:
    from utils.router_ai import router_ai
except ImportError:
    router_ai = None

class LeadHunter:
    def __init__(self, db: HunterDatabase):
        self.db = db
        self.geo_keywords = [
            "москва", "мск", "подмосковье", "мо", "жк", "корпус", "ремонт в москве",
            "нежилое помещение", "коммерция", "антресоль", "отдельный вход", "общепит",
            "кафе", "офис", "изменение назначения",
        ]

    async def hunt(self, messages: List[Dict]):
        results = []
        for msg in messages:
            analysis = await self._analyze_intent(msg['text'])
            if analysis['is_lead']:
                lead_data = {
                    'url': msg['url'], 'content': msg['text'],
                    'intent': analysis['intent'], 'hotness': analysis['hotness'],
                    'geo': "Москва/МО" if self._check_geo(msg['text']) else "Не указано",
                    'context_summary': analysis['context_summary']
                }
                if await self.db.save_lead(lead_data):
                    results.append(lead_data)
        return results

    def _check_geo(self, text: str) -> bool:
        return any(kw in text.lower() for kw in self.geo_keywords)

    async def _analyze_intent(self, text: str) -> Dict:
        if not router_ai:
            return {"is_lead": "ищу" in text.lower(), "intent": "Поиск", "hotness": 3, "context_summary": "AI offline"}

        prompt = f"Проанализируй сообщение: {text}. Если это запрос услуги (дизайн/перепланировка) - is_lead: true. Выдай JSON: is_lead, intent, hotness (1-5), context_summary"
        try:
            response = await router_ai.generate_response(prompt, model="kimi")
            return json.loads(re.search(r'\{.*\}', response, re.DOTALL).group(0))
        except Exception:
            return {"is_lead": False, "intent": "error", "hotness": 0, "context_summary": "ошибка анализа"}
