"""
Creative Agent — генерация идей контента и анализ трендов.
Специализация: Согласование перепланировок и переустройства помещений.
"""
import os
import re
import logging
from typing import List, Dict, Optional
from datetime import datetime
from utils.knowledge_base import KnowledgeBase
from utils import router_ai, yandex_gpt

logger = logging.getLogger(__name__)

# Стиль для генерации изображений
STYLE_PRESET = (
    "Architectural minimalism: clean lines, professional floor plans, "
    "combined with hyper-realistic interior photography. High-end real estate aesthetic. "
    "No prices in text. Focal point on spatial solutions."
)


class CreativeAgent:
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
        logger.info("🔍 CreativeAgent: поиск трендовых тем...")
        
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

            # СНАЧАЛА YandexGPT (в РФ, работает!)
            try:
                response = await yandex_gpt.generate_response(
                    user_prompt=user_prompt,
                    system_prompt=system_prompt.format(date=datetime.now().strftime("%B %Y")),
                    max_tokens=500
                )
                if response:
                    return self._parse_response(response, query)
            except Exception as e:
                logger.warning(f"YandexGPT error: {e}")
            
            # Fallback на Router AI
            if self.use_router:
                try:
                    response = await router_ai.generate_response(
                        user_prompt=user_prompt,
                        system_prompt=system_prompt.format(date=datetime.now().strftime("%B %Y")),
                        max_tokens=500
                    )
                    if response:
                        return self._parse_response(response, query)
                except Exception as e:
                    logger.warning(f"Router AI error: {e}")
                
        except Exception as e:
            logger.error(f"Creative AI error: {e}")
        
        # Fallback — возвращаем шаблонную тему
        return {
            "query": query,
            "title": f"Как согласовать {query} в 2026 году",
            "why": "Изменения в законодательстве делают это актуальным",
            "insight": "Специалисты знают нюансы, которые спасут от штрафов",
            "source": "template"
        }
    
    def _normalize_title(self, raw: str) -> str:
        """Убирает дубли номеров и лишние кавычки из заголовка (например «1. 1. «Тема»» → «Тема»)."""
        if not raw or not isinstance(raw, str):
            return raw or ""
        s = raw.strip()
        # Убрать ведущий номер типа "1. " или "2. "
        s = re.sub(r"^\d+\.\s*", "", s)
        # Убрать обрамляющие кавычки « »
        if s.startswith("«") and s.endswith("»"):
            s = s[1:-1].strip()
        if s.startswith('"') and s.endswith('"'):
            s = s[1:-1].strip()
        return s.strip() or raw

    def _parse_response(self, response: str, query: str) -> Dict:
        """Парсит ответ ИИ"""
        lines = [l.strip() for l in response.strip().split('\n') if l.strip()]
        title = lines[0] if lines else f"Тема: {query}"
        title = self._normalize_title(title)
        return {
            "query": query,
            "title": title,
            "why": lines[1] if len(lines) > 1 else "",
            "insight": lines[2] if len(lines) > 2 else "",
            "source": "ai"
        }

    async def ideas_from_spy_leads(
        self,
        leads: List[Dict],
        count: int = 3,
        trends: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        """
        Темы на базе трендов: анализ запросов лидов → острая проблема дня → пост-решение.
        trends: результат get_top_trends() (topic, count, percent) для аналитики креативщика.
        """
        if not leads:
            return await self.scout_topics(count)
        n = len(leads)
        logger.info("🔍 CreativeAgent: анализ %s запросов лидов → пост-решение...", n)
        context_parts = []
        for i, lead in enumerate(leads[:50], 1):
            text = (lead.get("text") or "").strip()
            source = lead.get("source_name") or lead.get("source_type") or ""
            if text:
                context_parts.append(f"[{i}] ({source})\n{text[:350]}")
        context = "\n\n".join(context_parts)[:5000]
        trends_line = ""
        if trends:
            parts = [f"{t['topic']} {t['percent']}%" for t in trends[:8]]
            trends_line = f"\nПо аналитике трендов за период: {', '.join(parts)}. Учти при выборе острой проблемы.\n\n"
        system_prompt = """Ты — эксперт по контенту в нише согласования перепланировок в РФ.

Твоя задача: проанализировать запросы лидов (вопросы и боли из чатов), выделить самую острую проблему дня и предложить пост-решение, который закроет этот вопрос.

Не придумывай темы «из головы» — опирайся на реальные запросы. Один блок = одна острая проблема + пост-решение по ней.

Формат ответа: по одному блоку на тему, в каждом блоке 3 строки:
Строка 1 — заголовок поста-решения (коротко, без номера и кавычек)
Строка 2 — почему это боль сейчас (по запросам)
Строка 3 — ключевой инсайт/решение
Между блоками — пустая строка. Дай 3 таких пост-решения по разным острым проблемам из запросов."""

        user_prompt = f"""Проанализируй эти {n} запросов лидов. Выдели самую острую проблему дня (и ещё 2 заметные) и напиши пост-решение по каждой, которое закроет вопрос.
{trends_line}
Запросы лидов:

{context}

Итог: 3 блока (заголовок, почему важно, инсайт). Заголовок — без нумерации в начале."""

        try:
            response = await yandex_gpt.generate_response(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=800
            )
            if response:
                return self._parse_ideas_response(response)
        except Exception as e:
            logger.warning(f"YandexGPT ideas_from_spy_leads: {e}")
        if self.use_router:
            try:
                response = await router_ai.generate_response(
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                    max_tokens=800
                )
                if response:
                    return self._parse_ideas_response(response)
            except Exception as e:
                logger.warning(f"Router AI ideas_from_spy_leads: {e}")
        return await self.scout_topics(count)

    def _parse_ideas_response(self, response: str) -> List[Dict]:
        """Парсит ответ с 3 темами (блоки из 3 строк: заголовок, почему, инсайт)."""
        blocks = []
        current = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if not line:
                if current:
                    title = self._normalize_title(current[0]) if current else ""
                    blocks.append({
                        "query": "",
                        "title": title,
                        "why": current[1] if len(current) > 1 else "",
                        "insight": current[2] if len(current) > 2 else "",
                        "source": "ai"
                    })
                    current = []
            else:
                current.append(line)
        if current:
            title = self._normalize_title(current[0]) if current else ""
            blocks.append({
                "query": "",
                "title": title,
                "why": current[1] if len(current) > 1 else "",
                "insight": current[2] if len(current) > 2 else "",
                "source": "ai"
            })
        while len(blocks) < 3:
            blocks.append({
                "query": "",
                "title": f"Тема {len(blocks) + 1} (сгенерируйте вручную)",
                "why": "",
                "insight": "",
                "source": "template"
            })
        return blocks[:3]
    
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

    async def analyze_trends(self):
        """Анализ трендов в перепланировках"""
        logger.info("📊 CreativeAgent: анализ трендов...")
        # В будущем здесь будет AI-анализ новостей
        return ["Цифровизация согласований", "Ужесточение требований к мокрым зонам", "Легализация через суд"]


# Singleton
creative_agent = CreativeAgent()


async def scout_content_ideas(count: int = 3) -> List[Dict]:
    """Удобная функция для поиска тем"""
    return await creative_agent.scout_topics(count)
