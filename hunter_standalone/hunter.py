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
        # Ключевые фразы DIY/ремонт — «народные» запросы на перепланировку
        self.lead_phrases = [
            "своими руками",
            "сломали стену",
            "перенесли радиатор",
            "залили пол",
            "хотим объединить",
        ]

    async def hunt(self, messages: List[Dict]):
        results = []
        for msg in messages:
            text = (msg.get('text') or '').strip()
            text_lower = text.lower()
            has_lead_phrase = any(p in text_lower for p in self.lead_phrases)
            analysis = await self._analyze_intent(msg.get('text', ''))
            hotness = max(analysis.get('hotness', 3), 4 if has_lead_phrase else 0)

            # Приоритет и стадия боли
            pain_stage = analysis.get("pain_stage", "ST-2" if hotness >= 3 else "ST-1")
            if has_lead_phrase:
                pain_stage = "ST-3"

            if hotness >= 2 or analysis.get('is_lead') or has_lead_phrase:
                lead_data = {
                    'url': msg.get('url', ''),
                    'content': text,
                    'intent': analysis.get('intent', 'DIY/ремонт') if has_lead_phrase else analysis.get('intent', '—'),
                    'hotness': hotness,
                    'geo': "Москва/МО" if self._check_geo(msg.get('text', '')) else "Не указано",
                    'context_summary': analysis.get('context_summary', '') or ('по фразе: ' + next((p for p in self.lead_phrases if p in text_lower), '')),
                    'recommendation': analysis.get('recommendation', ''),
                    'pain_level': analysis.get('pain_level', min(hotness, 5)),
                    'pain_stage': pain_stage,
                    'priority_score': hotness * 2 if hotness <= 5 else hotness,
                }
                if await self.db.save_lead(lead_data):
                    results.append(lead_data)
        return results

    def _check_geo(self, text: str) -> bool:
        return any(kw in (text or "").lower() for kw in self.geo_keywords)

    async def _analyze_intent(self, text: str) -> Dict:
        if not text or not (text or "").strip():
            return {"is_lead": False, "intent": "", "hotness": 0, "context_summary": ""}
        # Умный Охотник v2.0: приоритет — Агент-Шпион (Yandex AI Studio)
        try:
            from utils.yandex_ai_agents import call_spy_agent
            spy = await call_spy_agent(text)
            hotness = spy.get("hotness", 3)
            return {
                "is_lead": hotness >= 2,
                "intent": spy.get("recommendation", "")[:200] or "Запрос по перепланировке",
                "hotness": hotness,
                "context_summary": spy.get("recommendation", "")[:300],
                "recommendation": spy.get("recommendation", ""),
                "pain_level": spy.get("pain_level", min(hotness, 5)),
                "pain_stage": spy.get("pain_stage"),
            }
        except Exception:
            pass
        if not router_ai:
            return {"is_lead": "ищу" in text.lower(), "intent": "Поиск", "hotness": 3, "context_summary": "AI offline", "recommendation": "", "pain_level": 3}

        prompt = f"Проанализируй сообщение: {text}. Если это запрос услуги (дизайн/перепланировка) - is_lead: true. Выдай JSON: is_lead, intent, hotness (1-5), context_summary"
        try:
            response = await router_ai.generate_response(prompt, model="kimi")
            out = json.loads(re.search(r'\{.*\}', response, re.DOTALL).group(0))
            out.setdefault("recommendation", out.get("context_summary", ""))
            out.setdefault("pain_level", min(out.get("hotness", 3), 5))
            return out
        except Exception:
            return {"is_lead": False, "intent": "error", "hotness": 0, "context_summary": "ошибка анализа", "recommendation": "", "pain_level": 3}
