import os
import re
import json
import asyncio
from typing import List, Dict, Optional
from database import HunterDatabase

# Импортируем существующий клиент из основного проекта (если доступен)
try:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from ТЕРИОН.utils.router_ai import router_ai
except ImportError:
    router_ai = None
    print("⚠️ Router AI клиент не найден. Используется режим эмуляции.")

class LeadHunter:
    """Модуль Lead Hunter (Шпион)"""

    def __init__(self, db: HunterDatabase):
        self.db = db
        self.geo_keywords = ["москва", "мск", "подмосковье", "мо", "жк", "корпус", "ремонт в москве"]

    async def hunt(self, messages: List[Dict]):
        """Основная функция сканирования и анализа сообщений"""
        results = []
        for msg in messages:
            # 1. ГЕО-фильтрация (приоритет Москва)
            geo_found = self._check_geo(msg['text'])

            # 2. NLP Анализ Намерения (Intent) и Боли через AI
            analysis = await self._analyze_intent(msg['text'])

            if analysis['is_lead']:
                lead_data = {
                    'url': msg['url'],
                    'content': msg['text'],
                    'intent': analysis['intent'],
                    'hotness': analysis['hotness'],
                    'geo': geo_found or "Не определено",
                    'context_summary': analysis['context_summary']
                }

                # 3. Сохранение в БД (Анти-спам встроен в save_lead)
                is_new = await self.db.save_lead(lead_data)
                if is_new:
                    results.append(lead_data)

        return results

    def _check_geo(self, text: str) -> Optional[str]:
        """Гео-привязка (Москва и МО)"""
        text_lower = text.lower()
        for kw in self.geo_keywords:
            if kw in text_lower:
                return "Москва/МО"
        return None

    async def _analyze_intent(self, text: str) -> Dict:
        """Анализ намерения (intent) и извлечение боли через Router AI"""
        if not router_ai or not router_ai.api_key:
            return self._mock_analysis(text)

        prompt = f"""
Проанализируй сообщение из чата по теме ремонта:
"{text}"

Твоя задача:
1. Определить, является ли это запросом от КЛИЕНТА, который ищет услуги (дизайн, перепланировка, ремонт).
2. Если это РЕКЛАМА от дизайнера или спам — поставь is_lead: false.
3. Если это клиент:
   - intent: краткая суть (например, "Поиск дизайнера", "Вопрос по сносу стены")
   - hotness: степень горячести от 1 до 5 (5 — готов купить сейчас, 1 — просто спрашивает теорию)
   - context_summary: краткое описание "боли" или ситуации клиента для менеджера по продажам.

Ответь в формате JSON:
{{"is_lead": bool, "intent": "string", "hotness": int, "context_summary": "string"}}
"""
        try:
            response = await router_ai.generate_response(prompt, model="kimi")
            # Очистка от markdown если есть
            json_str = re.search(r'\{.*\}', response, re.DOTALL).group(0)
            return json.loads(json_str)
        except Exception as e:
            print(f"❌ AI Analysis error: {e}")
            return self._mock_analysis(text)

    def _mock_analysis(self, text: str) -> Dict:
        """Эмуляция анализа (если AI недоступен)"""
        text_lower = text.lower()
        if any(kw in text_lower for kw in ["ищу", "нужен", "посоветуйте", "подскажите"]):
            return {
                "is_lead": True,
                "intent": "Поиск специалиста",
                "hotness": 3,
                "context_summary": f"Пользователь интересуется: {text[:50]}..."
            }
        return {"is_lead": False, "intent": "None", "hotness": 0, "context_summary": ""}
