"""
Content Agent — модуль генерации контента для Telegram-каналов.

Генерирует посты, изображения и отчёты для каналов ТЕРИОН и ДОМ ГРАНД.
Использует Router AI (GPT) и Flux для генерации.
"""
import requests
import os
import logging
import random
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class ContentAgent:
    """Агент для генерации контента"""

    def __init__(self):
        self.folder_id = os.getenv("FOLDER_ID")
        self.api_key = os.getenv("ROUTER_AI_KEY") or os.getenv("YANDEX_API_KEY")
        self.image_api_key = os.getenv("ROUTER_AI_IMAGE_KEY") or self.api_key
        self.endpoint = os.getenv("ROUTER_AI_ENDPOINT", "https://api.router.ai/v1/completion")
        self.image_endpoint = os.getenv("ROUTER_AI_IMAGE_ENDPOINT", "https://api.router.ai/v1/image_generation")

        self.birthday_templates = [
            "Поздравляем вас с днем рождения! Пусть этот день будет наполнен радостью, теплом близких и приятными сюрпризами. Желаем крепкого здоровья, душевного равновесия и исполнения самых заветных желаний.",
            "С днем рождения! Пусть этот особенный день принесет вам море улыбок, тепла от родных и друзей, а также исполнение всех мечтаний. Желаем здоровья, счастья и благополучия на каждый день.",
            "Поздравляем с днем рождения! Пусть этот день будет ярким и незабываемым, наполненным любовью близких и приятными моментами. Желаем крепкого здоровья, семейного тепла и достижения всех поставленных целей.",
            "С днем рождения! Пусть этот праздник принесет вам заряд положительных эмоций, теплые объятия родных и исполнение желаний. Желаем здоровья, счастья и благополучия в вашей жизни.",
            "Поздравляем с днем рождения! Пусть этот день будет особенным, наполненным радостью, теплом и заботой близких. Желаем крепкого здоровья, душевного комфорта и исполнения всех мечтаний.",
            "С днем рождения! Пусть этот праздник станет началом новых радостных событий в вашей жизни. Желаем здоровья, счастья, семейного тепла и исполнения самых сокровенных желаний.",
            "Поздравляем с днем рождения! Пусть этот день будет ярким и незабываемым, а каждый новый день приносит новые возможности и радости. Желаем крепкого здоровья и благополучия.",
            "С днем рождения! Желаем вам тепла от близких, радости от маленьких побед и исполнения мечтаний. Пусть этот день станет одним из самых счастливых в вашей жизни."
        ]

    def build_image_prompt(self, post: dict) -> str:
        """Генерирует промпт для Flux"""
        post_type = post.get('type')
        channel = post.get('channel', 'terion')
        theme = post.get('theme', '')

        terion_prompts = {
            'экспертиза': "architectural visualization, blueprints, professional office, legal papers, corporate style, clean minimalist design, 4k resolution, no people, TERION brand colors",
            'живой': "modern apartment renovation Moscow, interior design, realistic lighting, open space kitchen living room, minimalist corporate style, 4k resolution, professional photography look",
            'новость': "Moscow construction news, architectural update, city building context, professional corporate style, technical aesthetic, 4k resolution, no people, clean business presentation",
            'поздравление': "elegant celebration background, warm golden lighting, festive decoration soft colors, cozy atmosphere, professional corporate TERION style, 4k resolution",
            'приветствие': "professional consultation office, modern workspace, clean minimalist design, TERION branding, 4k resolution, welcoming business atmosphere"
        }

        dom_grand_prompts = {
            'экспертиза': "construction site, building process, house renovation, technical details, blueprints on site, professional builder aesthetic, construction materials, 4k resolution, DOM GRAND style",
            'живой': "country house construction, rural property, building site progress, realistic working environment, construction team, modern rural architecture, 4k resolution, DOM GRAND branding",
            'новость': "building news rural, construction update, house project progress, technical construction photography, professional site documentation, 4k resolution, DOM GRAND aesthetic",
            'поздравление': "warm country house celebration, rural home atmosphere, festive construction site decoration, cozy home feeling, professional DOM GRAND style, 4k resolution",
            'приветствие': "construction company office, technical supervision workspace, building plans, professional builder setting, DOM GRAND branding, 4k resolution, welcoming atmosphere"
        }

        prompts = dom_grand_prompts if channel == 'dom_grand' else terion_prompts
        base_prompt = prompts.get(post_type, prompts['экспертиза'])

        if theme:
            base_prompt += f", theme: {theme}"

        return base_prompt

    def generate_posts(self, count=7, post_types=None, theme=None, channel='terion'):
        """Генерирует N постов"""
        if post_types is None:
            post_types = {'экспертиза': count - 1, 'живой': 1}

        posts = []
        start_date = datetime.now() + timedelta(days=1)
        start_date = start_date.replace(hour=10, minute=0, second=0)

        for post_type, num in post_types.items():
            for i in range(num):
                prompt = self._build_prompt(post_type, theme)
                text = self._call_yandex_gpt(prompt)
                title, body, cta = self._parse_response(text)

                post = {
                    'type': post_type,
                    'channel': channel,
                    'theme': theme,
                    'title': title,
                    'body': body,
                    'cta': cta,
                    'publish_date': start_date + timedelta(days=len(posts)),
                    'image_prompt': self.build_image_prompt({'type': post_type, 'channel': channel}),
                    'image_url': None
                }
                posts.append(post)

        return posts

    def _build_prompt(self, post_type, theme=None):
        """Формирует промпт для LLM"""
        season = self._get_season_context()
        theme_note = f"\nУчитывай тему недели: {theme}" if theme else ""

        CTA_TEXT = "Напишите нашему ИИ-помощнику Антону, и мы расскажем, что именно нужно сделать в вашей ситуации: @Parkhovenko_i_kompaniya_bot"

        prompts = {
            'экспертиза': f"""Создай экспертный пост для Telegram-канала по перепланировкам квартир в Москве.

Контекст сезона: {season}{theme_note}

Требования:
- Разбор одной конкретной нормы, процедуры или типичной ошибки
- 150–300 слов, экспертно, без воды
- Конкретный пример или кейс из практики
- Обязательный CTA: {CTA_TEXT}

Формат ответа:
[Заголовок или вопрос]

[Основной текст поста]

👉 {CTA_TEXT}""",
            'живой': f"""Создай «живой» пост для Telegram-канала по перепланировкам.

Контекст сезона: {season}{theme_note}

Требования:
- Привязка к текущим событиям
- 150–250 слов, по-человечески, с личной ноткой
- Мягкий переход к теме перепланировок
- Обязательный CTA: {CTA_TEXT}

Формат ответа:
[Сезонный зацеп]

[Связка с темой]

👉 {CTA_TEXT}""",
            'новость': f"""Создай новостной пост для Telegram-канала по перепланировкам.

Требования:
- Объявление об изменении норм
- 120–200 слов, кратко и чётко
- Что изменилось и чем это чревато
- Обязательный CTA: {CTA_TEXT}{theme_note}

Формат ответа:
[Новость простыми словами]

[Что это значит]

👉 {CTA_TEXT}""",
            'поздравление': f"""Напиши короткое искреннее поздравление с днём рождения.

Требования:
- 60-100 слов
- Тёплые пожелания счастья, здоровья, радости
- Пожелание уюта и тепла в доме
- Простой дружелюбный язык
- БЕЗ упоминания работы, услуг, бизнеса

Формат:
🎂 [Имя]

[Поздравление]"""
        }

        return prompts.get(post_type, prompts['экспертиза'])

    def _get_season_context(self):
        """Определяет сезонный контекст"""
        month = datetime.now().month
        contexts = {
            (12, 1, 2): "Зима: снег, отключения ЖКХ, утепление",
            (3, 4, 5): "Весна: отключение горячей воды, подготовка к ремонтному сезону",
            (6, 7, 8): "Лето: пик ремонтного сезона",
            (9, 10, 11): "Осень: включение отопления, завершение ремонтов"
        }
        for months, context in contexts.items():
            if month in months:
                return context
        return contexts[(12, 1, 2)]

    def _call_yandex_gpt(self, user_prompt):
        """Вызов LLM API"""
        system_prompt = """Ты — контент-менеджер Telegram-канала по перепланировкам квартир в Москве.

Задача: генерировать посты, которые прогревают к заявке в бота @Parkhovenko_i_kompaniya_bot.

Стиль: экспертно, по-деловому, без воды, с понятными примерами и чёткими CTA."""

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {self.api_key}",
            "x-folder-id": self.folder_id
        }

        payload = {
            "modelUri": f"gpt://{self.folder_id}/yandexgpt/latest",
            "completionOptions": {"stream": False, "temperature": 0.7, "maxTokens": 2000},
            "messages": [
                {"role": "system", "text": system_prompt},
                {"role": "user", "text": user_prompt}
            ]
        }

        try:
            response = requests.post(self.endpoint, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()['result']['alternatives'][0]['message']['text']
        except Exception as e:
            logger.error(f"Ошибка LLM: {e}")
            return f"Ошибка: {e}"

    def _parse_response(self, text):
        """Парсит ответ на title, body, cta"""
        lines = text.strip().split('\n')
        cta_line = None
        for i, line in enumerate(lines):
            if '👉' in line or 'CTA:' in line.upper():
                cta_line = i
                break

        if cta_line:
            cta = '\n'.join(lines[cta_line:]).strip()
            body_lines = lines[:cta_line]
        else:
            cta = ""
            body_lines = lines

        title = ""
        if body_lines and len(body_lines[0]) < 100:
            title = body_lines[0].strip('#').strip()
            body_lines = body_lines[1:]

        body = '\n'.join(body_lines).strip()
        return title, body, cta

    def generate_image(self, prompt: str) -> Optional[str]:
        """Генерирует изображение через Router AI / Flux"""
        try:
            from image_gen import generate
            return generate(prompt)
        except ImportError:
            logger.error("Модуль image_gen не найден")
            return None
        except Exception as e:
            logger.error(f"Ошибка генерации изображения: {e}")
            return None

    def generate_post_with_image(self, post_type: str, theme: str = None, channel: str = 'terion') -> dict:
        """Генерирует пост и изображение"""
        prompt = self._build_prompt(post_type, theme)
        text = self._call_yandex_gpt(prompt)
        title, body, cta = self._parse_response(text)

        post_dict = {'type': post_type, 'theme': theme, 'channel': channel}
        image_prompt = self.build_image_prompt(post_dict)
        image_url = self.generate_image(image_prompt)

        return {
            'type': post_type,
            'channel': channel,
            'theme': theme,
            'title': title,
            'body': body,
            'cta': cta,
            'image_prompt': image_prompt,
            'image_url': image_url
        }

    def generate_greeting_post(self, person_name=None, date=None, occasion='день рождения'):
        """Генерирует поздравление"""
        display_name = person_name if person_name else "наш подписчик"
        prompt = f"""Создай короткое искреннее поздравление.

Повод: {occasion}
Имя: {display_name}
Дата: {date}

Требования:
- 60-100 слов
- Тёплые пожелания
- БЕЗ продаж и услуг

Формат:
🎂 {display_name}

[Поздравление]"""

        text = self._call_yandex_gpt(prompt)

        # Проверяем на продажи
        banned = ["ремонт", "перепланиров", "услуг", "консультац", "бот", "скидк"]
        if any(word in text.lower() for word in banned):
            text = random.choice(self.birthday_templates)
            text = f"🎂 {display_name}\n\n{text}"

        title, body, cta = self._parse_response(text)
        return {'type': 'поздравление', 'title': title, 'body': body, 'cta': cta}

    def generate_welcome_post(self, person_name=None):
        """Генерирует приветствие"""
        display_name = person_name if person_name else "новый подписчик"
        prompt = f"""Создай приветственное сообщение.

Адресат: {display_name}

Требования:
- 80-120 слов
- Кратко представить канал
- 1-2 примера ситуаций
- CTA к боту @Parkhovenko_i_kompaniya_bot

Формат:
👋 {display_name}

[Текст 2-3 абзаца]"""

        text = self._call_yandex_gpt(prompt)
        title, body, cta = self._parse_response(text)
        return {'type': 'приветствие', 'title': title, 'body': body, 'cta': cta}
