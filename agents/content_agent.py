import requests
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class ContentAgent:
    def __init__(self):
        from utils.yandex_gpt import yandex_gpt
        from database.db import db
        self.gpt = yandex_gpt
        self.db = db
        self.brief_content = self._load_brief()

    def _load_brief(self):
        """Загружает базу знаний"""
        paths = ["BRIEF_pereplanirovki.md", "docs/09_ИИ_консультант/Промпт_ИИ_консультанта.md"]
        for path in paths:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception as e:
                    logger.error(f"Error loading brief from {path}: {e}")
        return "База знаний не найдена. Используйте общие знания по перепланировкам в Москве."

    async def _is_duplicate(self, topic: str, title: str) -> bool:
        """Проверка на дубликаты за последние 48 часов"""
        async with self.db.conn.cursor() as cursor:
            # Проверяем по заголовку и теме в content_plan
            await cursor.execute(
                """SELECT COUNT(*) FROM content_plan 
                   WHERE (title = ? OR theme = ?) 
                   AND created_at >= datetime('now', '-48 hours')""",
                (title, topic)
            )
            row = await cursor.fetchone()
            return row[0] > 0 if row else False

    async def generate_post(self, topic: str, force_angle: Optional[str] = None) -> Dict:
        """Генерирует текст поста через YandexGPT с проверкой на дубликаты"""
        
        # Базовая проверка (в реальности title может генерироваться отдельно, 
        # здесь мы используем topic как theme)
        if await self._is_duplicate(topic, topic) and not force_angle:
            logger.info(f"Тема '{topic}' уже предлагалась недавно. Меняем угол обзора.")
            force_angle = "кейс или практический пример вместо общих советов"

        angle_instruction = f"\nУгол обзора: {force_angle}" if force_angle else ""

        system_prompt = f"""
Ты — экспертный контент-менеджер компании GEORIS (ИП Пархоменко). 
Твоя задача: написать пост для Telegram-канала о перепланировках в Москве.

Тема: {topic}{angle_instruction}

Стиль: Профессиональный, но доступный. Экспертный, вызывающий доверие. 
Тон: ГЕОРИС — надежность, законность, экспертность.

База знаний:
{self.brief_content[:2000]}

Требования:
1. Текст должен быть структурированным (используй абзацы).
2. Используй эмодзи умеренно.
3. В конце обязательно добавь призыв к действию (CTA): «📝 Записаться на консультацию».
4. Не используй сложные юридические термины без объяснения.
5. Проверь текст на грамматику и соответствие тону ГЕОРИС.
""".strip()

        try:
            result_text = await self.gpt.generate_response(
                user_prompt=f"Напиши экспертный пост на тему: {topic}. Обязательно начни с цепляющего заголовка.",
                system_prompt=system_prompt,
                temperature=0.6,
                max_tokens=1500
            )
            
            # Извлекаем заголовок (первая строка)
            lines = result_text.strip().split('\n')
            title = lines[0].replace('#', '').strip()
            body = '\n'.join(lines[1:]).strip()
            
            return {
                "title": title,
                "body": body,
                "topic": topic,
                "status": "draft" # Посты приходят на одобрение
            }
        except Exception as e:
            logger.error(f"Error generating post: {e}")
            return {
                "title": "Ошибка генерации",
                "body": f"Ошибка при генерации поста на тему '{topic}'.",
                "topic": topic,
                "status": "error"
            }

    async def create_posts_from_interview(
        self,
        voice_text: str,
        count: int = 2
    ) -> List[Dict]:
        """
        Создаёт черновики постов из голосового интервью/заметки.
        Автоопределяет канал: ГЕОРИС или Дом Гранд.

        Args:
            voice_text: Расшифрованный текст голосового сообщения
            count: Количество постов

        Returns:
            Список словарей: title, body, channel, thread_id
        """
        import os

        thread_drafts = int(os.getenv("THREAD_ID_DRAFTS", "85"))

        # Определяем канал по ключевым словам
        text_lower = voice_text.lower()
        if any(w in text_lower for w in ["студия", "инвест", "дом гранд", "апартамент"]):
            channel = "Дом Гранд"
            style = "золотисто-деловой, про инвестиции и премиум-перепланировки"
        elif any(w in text_lower for w in ["бти", "мжи", "предписание", "согласован", "георис"]):
            channel = "ГЕОРИС"
            style = "экспертный синий, про согласование и юридическую часть"
        else:
            channel = "ГЕОРИС"
            style = "экспертный, про перепланировки в Москве"

        system_prompt = (
            f"Ты — контент-редактор компании по перепланировкам. "
            f"Стиль канала: {style}. "
            f"Создай {count} поста для Telegram на основе заметки эксперта. "
            f"Каждый пост: цепляющий заголовок + 3-5 абзацев + призыв к действию. "
            f"Отвечай строго в JSON: "
            f'[{{"title": "...", "body": "...", "channel": "{channel}"}}]'
        )

        user_prompt = (
            f"Заметка эксперта:\n{voice_text}\n\n"
            f"Создай {count} готовых поста. "
            f"Используй живой язык, конкретные примеры из заметки, "
            f"заканчивай призывом написать в бот или позвонить."
        )

        try:
            response = await self.gpt.generate_response(
                user_prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.75,
                max_tokens=2000
            )
            match = __import__('re').search(r'\[.*\]', response, __import__('re').DOTALL)
            if match:
                posts = __import__('json').loads(match.group(0))
                # Добавляем thread_id к каждому посту
                for p in posts:
                    p['thread_id'] = thread_drafts
                    p['status'] = 'draft'
                return posts[:count]
            logger.error(f"create_posts_from_interview: не удалось распарсить JSON: {response}")
            return []
        except Exception as e:
            logger.error(f"create_posts_from_interview error: {e}")
            return []

content_agent = ContentAgent()
