import logging
import os
from utils import router_ai

logger = logging.getLogger(__name__)

class LeadAnalyzer:
    """AI-анализ постов на основе Базы Знаний 'Друга-эксперта'"""
    
    def __init__(self):
        self.kb_path = "knowledge_base/sales/hunter_manual.md"
        
    async def analyze_post(self, text: str) -> dict:
        """
        Анализирует пост, сверяясь с базой знаний продаж.
        Возвращает dict с оценкой (1-10) и стадией боли (ST-1...ST-4).
        """
        if text is None:
            text = ""
        text = (text or "").strip()
        logger.info("🧠 LeadAnalyzer: глубокий анализ через Базу Знаний...")

        # 1. Читаем ваши инструкции
        manual = ""
        if os.path.exists(self.kb_path):
            with open(self.kb_path, 'r', encoding='utf-8') as f:
                manual = f.read()

        # 2. Если пост совсем короткий или пустой
        if len(text) < 10:
            return {"priority_score": 0, "pain_stage": "ST-1", "is_lead": False}

        # 3. Формируем запрос к Антону (ИИ)
        prompt = f"""
        Инструкция для оценки: {manual}
        
        Текст сообщения из чата: "{text}"
        
        Твоя задача:
        Проанализируй сообщение и классифицируй его по шкале от 1 до 10 и присвой категорию боли:
        - ST-1 (Инфо): Просто интересуется теорией.
        - ST-2 (Планирование): Собирается делать ремонт, ищет варианты.
        - ST-3 (Актив): Уже делает ремонт, боится штрафов.
        - ST-4 (Критично): Получил предписание, пришла инспекция, суд, блокировка сделки.

        Верни ответ ТОЛЬКО в формате JSON:
        {{
            "priority_score": число от 1 до 10,
            "pain_stage": "ST-1" | "ST-2" | "ST-3" | "ST-4",
            "justification": "краткое пояснение, почему выбрана эта стадия"
        }}
        """
        
        try:
            response = await router_ai.generate_response(prompt)
            if response is None or not (response and str(response).strip()):
                raise ValueError("Router AI вернул пустой ответ")

            import json, re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if not match:
                raise ValueError(f"Не удалось найти JSON в ответе: {response}")

            data = json.loads(match.group(0))
            data["is_lead"] = data.get("priority_score", 0) >= 5
            logger.info(f"🎯 Оценка лида: {data}")
            return data
        except Exception as e:
            logger.error(f"❌ Ошибка анализатора: {e}")
            # Fallback: если ИИ упал, ищем ключевые слова вручную
            triggers = ["предписание", "суд", "инспекция", "мжи", "штраф"]
            if text and any(word in text.lower() for word in triggers):
                return {"priority_score": 9, "pain_stage": "ST-4", "is_lead": True, "justification": "Fallback: найдены критические ключевые слова"}

            triggers_med = ["мокрая точка", "узаконить", "перепланиров"]
            if text and any(word in text.lower() for word in triggers_med):
                return {"priority_score": 7, "pain_stage": "ST-3", "is_lead": True, "justification": "Fallback: найдены технические ключевые слова"}

            return {"priority_score": 1, "pain_stage": "ST-1", "is_lead": False, "justification": "Fallback: низкий приоритет по умолчанию"}
