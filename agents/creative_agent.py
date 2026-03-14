"""
<<<<<<< HEAD
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
=======
Creative Agent — генерация идей контента и анализ трендов.
Специализация: Согласование перепланировок и переустройства помещений.
"""
import os
import re
import logging
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
from utils.knowledge_base import KnowledgeBase
from utils import router_ai, yandex_gpt

logger = logging.getLogger(__name__)

# --- СТИЛЬ 2026: Адаптивный стиль для визуалов 2026 года ---
STYLE_PRESET = (
    "2026-style realistic interior photography or technical floor plan matching the text. "
    "The image must EXACTLY match the post topic and content. "
    "For mass housing topics (ЖК, хрущевка, ПИК, Самолет): show modern 2026 apartment layouts, "
    "contemporary renovation examples, or technical floor plans with current building codes. "
    "For technical topics: show diagrams, floor plans, or construction details in 2026 style. "
    "For legal/regulatory topics: show official document style, legal papers, or Moscow cityscape with government buildings. "
    "For general topics: show relevant interior spaces or architectural solutions in contemporary 2026 design. "
    "For news topics: Realistic cityscape of Moscow 2026 or official document style. No interior renders. "
    "Style: Modern, clean, professional. Use contemporary color palettes and lighting. "
    "No abstract elements, no luxury bias, no mansions unless specifically required by the topic. "
    "Focal point on spatial solutions and practical examples. No people, no text on image."
)

class CreativeAgent:
    """Агент для поиска трендовых тем и трендсеттинга"""
    
    def __init__(self):
        # Приоритет Yandex для РФ, так как он лучше знает наши законы
        self.yandex_key = os.getenv("YANDEX_API_KEY")
        self.router_api_key = os.getenv("ROUTER_AI_KEY")
        self.use_router = bool(self.router_api_key)
        self.kb = KnowledgeBase()
        # Ссылка на квиз из конфига
        self.quiz_link = os.getenv("VK_QUIZ_LINK", "https://t.me/Parkhovenko_i_kompaniya_bot?start=quiz")
    
    async def scout_topics(self, count: int = 3) -> List[Dict]:
        """Ищет трендовые темы (добавлен фокус на массовый сегмент)"""
        logger.info("🔍 CreativeAgent: поиск трендовых тем (Массовый сегмент + ГОСТ)...")
        
        topics = []
        # Тема 1: Массовая застройка (ПИК/Самолет)
        topic1 = await self._research_topic("перепланировка в новостройках ПИК и Самолет 2026, особенности")
        topics.append(topic1)
        
        # Тема 2: Технические нюансы (Подоконные блоки/Мокрые зоны)
        topic2 = await self._research_topic("демонтаж подоконного блока и объединение лоджии: новые правила 2026")
        topics.append(topic2)
        
        # Тема 3: Юридическая база
        topic3 = await self._research_topic("предписания Мосжилинспекции и как их избежать")
        topics.append(topic3)
        
        return topics

    async def _research_topic(self, query: str) -> Dict:
        """Исследует тему и формирует ТЗ для поста с ФУТЕРОМ"""
        kb_context = ""
        try:
            chunks = await self.kb.get_context(query, max_chunks=3)
            if chunks:
                kb_context = chunks[:500] if isinstance(chunks, str) else ""
        except Exception as e:
            logger.warning(f"KnowledgeBase error: {e}")

        # Определяем, является ли тема новостью (расширенная детекция)
        query_lower = query.lower()
        is_news = (
            'новости' in query_lower or 
            'новость' in query_lower or 
            'ипотека' in query_lower or 
            'закон' in query_lower or 
            'мжи' in query_lower or
            query_lower.startswith('news')
        )
        
        # --- ИСПРАВЛЕНИЕ: Жесткое требование к КВИЗУ и ХЭШТЕГАМ в системном промпте ---
        system_prompt = f"""Ты — эксперт TERION по согласованию перепланировок.
Твоя задача — создать пост, который продает экспертность Юлии Владимировны Пархоменко.

ОБЯЗАТЕЛЬНАЯ СТРУКТУРА:
1. Заголовок (без кавычек и цифр)
2. Проблема и решение (коротко, экспертно)
3. ИНСАЙТ
4. ФУТЕР (Призыв к действию):
🧐 Узнайте стоимость вашей перепланировки за 1 минуту:
👉 {self.quiz_link}

#перепланировка #МЖИ #БТИ #TERION #согласование #Москва #МО

КРИТИЧЕСКИ ВАЖНО:
- Оптимальный объем текста — от 600 до 1000 знаков. Пост должен быть логически завершен.
- ЗАПРЕЩЕНО обрывать текст на полуслове. Если лимит символов исчерпан, сокращай вводную часть, но не финал.
- Используй короткие абзацы для лучшей читаемости.
{f"- РЕЖИМ НОВОСТИ: Для новостей ЗАПРЕЩЕНО выдумывать цифры и условия. Если точных данных в Базе Знаний нет, пиши только подтвержденную информацию о событии без домыслов." if is_news else ""}"""

        user_prompt = f"""Тема: {query}\nКонтекст: {kb_context}\nСоздай экспертный пост."""

        # Логика генерации (Yandex -> Router) остается прежней, но теперь с новым промптом
        # max_tokens=800 для исключения технических обрывов
        try:
            response = await yandex_gpt.generate_response(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                max_tokens=800
            )
            if response:
                return self._parse_response(response, query)
        except Exception as e:
            logger.warning(f"YandexGPT error: {e}")
        
        # Fallback на Router AI, если Yandex не сработал
        if self.use_router:
            try:
                response = await router_ai.generate_response(
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                    max_tokens=800
                )
                if response:
                    return self._parse_response(response, query)
            except Exception as e:
                logger.warning(f"Router AI error: {e}")
            
        return {
            "query": query,
            "title": f"Важное о {query}",
            "body": "Текст генерируется...",
            "cta": f"Пройдите квиз: {self.quiz_link}",
            "source": "template"
        }
    
    def _parse_response(self, response: str, query: str) -> Dict:
        """Парсит ответ ИИ и извлекает структурированные данные поста"""
        if not response:
            return {
                "query": query,
                "title": f"Важное о {query}",
                "body": "Текст генерируется...",
                "cta": f"Пройдите квиз: {self.quiz_link}",
                "source": "template"
            }
        
        # Извлекаем текст ответа
        text = response.strip()
        
        # Разбиваем на строки
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        # Первая строка — заголовок
        title = lines[0] if lines else f"Важное о {query}"
        # Убираем нумерацию и кавычки из заголовка
        title = re.sub(r'^\d+\.\s*', '', title)
        title = re.sub(r'^["«](.*)["»]$', r'\1', title)
        title = title.strip()
        
        # Остальные строки — тело поста
        body_lines = lines[1:] if len(lines) > 1 else []
        body = "\n\n".join(body_lines) if body_lines else text
        
        # Проверяем, есть ли уже ссылка на квиз в тексте
        has_quiz = self.quiz_link in body or "квиз" in body.lower()
        
        # Формируем CTA
        if has_quiz:
            cta = ""
        else:
            cta = f"🧐 Узнайте стоимость вашей перепланировки за 1 минуту:\n👉 {self.quiz_link}"
        
        return {
            "query": query,
            "title": title,
            "body": body,
            "cta": cta,
            "source": "ai"
        }
    
    async def generate_base_expert_pack(self) -> List[Dict]:
        """
        Генерирует "Base Expert Pack" — первые 9 постов для запуска контент-воронки.
        
        Фокус на:
        - Доверие (экспертность Юлии, опыт TERION)
        - Кейсы (московские ЖК: Зиларт, Династия, Символ и др.)
        - Регуляции 2026 года (новые правила, изменения в законодательстве)
        
        Returns:
            List[Dict]: Список из 9 постов с полями title, body, cta, theme, image_prompt
        """
        logger.info("🎯 CreativeAgent: генерация Base Expert Pack (9 постов)...")
        
        # ── ТЕМЫ ДЛЯ BASE EXPERT PACK ────────────────────────────────────────────────
        base_topics = [
            # 1-3: Доверие и экспертность
            {
                "query": "Кто такая Юлия Пархоменко и почему TERION — эксперт по перепланировкам в Москве",
                "theme": "trust_expertise",
                "focus": "доверие"
            },
            {
                "query": "Сколько перепланировок согласовала TERION в Москве: реальные цифры и кейсы",
                "theme": "trust_cases",
                "focus": "доверие"
            },
            {
                "query": "Почему собственники выбирают TERION для согласования перепланировок: отзывы и результаты",
                "theme": "trust_reputation",
                "focus": "доверие"
            },
            # 4-6: Кейсы московских ЖК
            {
                "query": "Перепланировка в ЖК Зиларт: как TERION помогла узаконить объединение кухни и гостиной",
                "theme": "case_zilart",
                "focus": "кейсы"
            },
            {
                "query": "Согласование перепланировки в ЖК Династия: перенос мокрой зоны и объединение комнат",
                "theme": "case_dynasty",
                "focus": "кейсы"
            },
            {
                "query": "Узаконивание перепланировки в ЖК Символ: работа с предписанием МЖИ и согласование с БТИ",
                "theme": "case_symbol",
                "focus": "кейсы"
            },
            # 7-9: Регуляции 2026 года
            {
                "query": "Новые правила перепланировок в Москве 2026: что изменилось в законодательстве",
                "theme": "regulations_2026",
                "focus": "регуляции"
            },
            {
                "query": "Изменения в требованиях Мосжилинспекции 2026: как избежать штрафов и предписаний",
                "theme": "regulations_mji",
                "focus": "регуляции"
            },
            {
                "query": "Обновленные нормы БТИ для перепланировок 2026: новые требования к проектной документации",
                "theme": "regulations_bti",
                "focus": "регуляции"
            },
        ]
        
        posts = []
        for i, topic_info in enumerate(base_topics, 1):
            try:
                logger.info(f"📝 Генерация поста {i}/9: {topic_info['theme']}")
                
                # Генерируем контент поста
                post_data = await self._research_topic(topic_info["query"])
                
                # Формируем image_prompt на основе темы и контента
                image_prompt = self._generate_image_prompt(post_data, topic_info)
                
                # Добавляем подпись эксперта в body
                expert_signature = "\n\n---\n🏡 Эксперт: Юлия Пархоменко\nКомпания: TERION"
                if expert_signature not in post_data.get("body", ""):
                    post_data["body"] = post_data.get("body", "") + expert_signature
                
                # Убеждаемся, что CTA содержит ссылку на квиз
                if not post_data.get("cta"):
                    post_data["cta"] = f"🧐 Узнайте стоимость вашей перепланировки за 1 минуту:\n👉 {self.quiz_link}"
                
                # Добавляем метаданные
                post_data["theme"] = topic_info["theme"]
                post_data["focus"] = topic_info["focus"]
                post_data["image_prompt"] = image_prompt
                
                posts.append(post_data)
                logger.info(f"✅ Пост {i}/9 сгенерирован: {post_data.get('title', 'Без названия')}")
                
                # Небольшая задержка между генерациями для избежания rate limits
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Ошибка генерации поста {i}/9 ({topic_info['theme']}): {e}")
                # Добавляем fallback пост
                posts.append({
                    "query": topic_info["query"],
                    "title": f"Важное о {topic_info['theme']}",
                    "body": f"Экспертный контент по теме: {topic_info['query']}\n\n{expert_signature}",
                    "cta": f"🧐 Узнайте стоимость вашей перепланировки за 1 минуту:\n👉 {self.quiz_link}",
                    "theme": topic_info["theme"],
                    "focus": topic_info["focus"],
                    "image_prompt": f"2026-style realistic interior or legal document related to {topic_info['theme']}",
                    "source": "fallback"
                })
        
        logger.info(f"✅ Base Expert Pack сгенерирован: {len(posts)} постов")
        return posts
    
    def _generate_image_prompt(self, post_data: Dict, topic_info: Dict) -> str:
        """
        Генерирует промпт для изображения на основе темы и контента поста.
        
        Args:
            post_data: Данные поста (title, body)
            topic_info: Информация о теме (theme, focus)
        
        Returns:
            str: Промпт для генерации изображения в стиле 2026 года
        """
        focus = topic_info.get("focus", "")
        theme = topic_info.get("theme", "")
        title = post_data.get("title", "")
        
        # Базовый промпт в стиле 2026 года
        base_prompt = "2026-style professional photography, "
        
        if focus == "доверие":
            # Для постов о доверии: современные интерьеры, офисные пространства, профессиональная атмосфера
            image_prompt = f"{base_prompt}modern professional interior, contemporary office space, expert consultation setting, clean and trustworthy atmosphere, natural lighting, no people, no text"
        elif focus == "кейсы":
            # Для кейсов: конкретные интерьеры ЖК, до/после перепланировки, технические планы
            if "зиларт" in theme.lower():
                image_prompt = f"{base_prompt}modern apartment interior in Zilart residential complex, contemporary renovation, open space kitchen-living room, Moscow 2026, realistic interior design, no people, no text"
            elif "династия" in theme.lower():
                image_prompt = f"{base_prompt}modern apartment interior in Dynasty residential complex, bathroom relocation, contemporary renovation, Moscow 2026, realistic interior design, no people, no text"
            elif "символ" in theme.lower():
                image_prompt = f"{base_prompt}modern apartment interior in Symbol residential complex, legal documents and floor plans, contemporary renovation, Moscow 2026, realistic interior design, no people, no text"
            else:
                image_prompt = f"{base_prompt}modern Moscow apartment interior, contemporary renovation example, realistic interior design 2026, no people, no text"
        elif focus == "регуляции":
            # Для регуляций: официальные документы, городские пейзажи Москвы, правительственные здания
            image_prompt = f"{base_prompt}official document style, legal papers, Moscow cityscape 2026, government buildings, professional legal documentation, realistic style, no people, no text"
        else:
            # Общий промпт
            image_prompt = f"{base_prompt}realistic interior or technical floor plan matching the text, contemporary 2026 design, professional photography, no people, no text"
        
        return image_prompt

# Создаем экземпляр агента для использования в других файлах
creative_agent = CreativeAgent()
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
