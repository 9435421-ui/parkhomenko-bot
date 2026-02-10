"""
Content Agent — асинхронный модуль генерации контента для Telegram-каналов.
Использует aiohttp для асинхронных запросов к Router AI (GPT).
"""
import aiohttp
import os
import logging
import random
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class ContentAgent:
    """Агент для генерации контента (async)"""

    def __init__(self):
        self.folder_id = os.getenv("FOLDER_ID")
        self.api_key = os.getenv("ROUTER_AI_KEY") or os.getenv("YANDEX_API_KEY")
        self.image_api_key = os.getenv("ROUTER_AI_IMAGE_KEY") or self.api_key
        self.endpoint = os.getenv("ROUTER_AI_ENDPOINT", "https://api.router.ai/v1/completion")
        
        # Fallback шаблоны на случай ошибок
        self.fallback_templates = {
            'экспертиза': {
                'title': '📋 Важная информация о перепланировке',
                'body': 'При перепланировке квартиры важно соблюдать установленные нормы и правила.\n\nОбратитесь к нашим экспертам за консультацией — мы поможем разобраться в тонкостях законодательства.',
                'cta': '👉 Записаться на консультацию: @Parkhovenko_i_kompaniya_bot'
            },
            'живой': {
                'title': '🏠 Новости ремонтного сезона',
                'body': 'Весна — время обновления! Многие собственники начинают ремонтные работы.\n\nПомните: любые изменения требуют согласования. Наши специалисты готовы помочь с подготовкой документов.',
                'cta': '👉 Получить консультацию: @Parkhovenko_i_kompaniya_bot'
            },
            'новость': {
                'title': '📢 Информация для собственников',
                'body': 'Напоминаем о необходимости соблюдения норм при проведении перепланировок.\n\nНесогласованные изменения могут повлечь штрафы и сложности с продажей недвижимости.',
                'cta': '👉 Узнать подробности: @Parkhovenko_i_kompaniya_bot'
            },
            'поздравление': {
                'title': '🎂 С праздником!',
                'body': 'Пусть этот день принесёт вам радость, тепло и уют в вашем доме!\n\nЖелаем здоровья, счастья и благополучия вашей семье.',
                'cta': ''
            },
            'приветствие': {
                'title': '👋 Добро пожаловать!',
                'body': 'Мы рады видеть вас в нашем канале!\n\nЗдесь вы найдёте полезную информацию о перепланировках, ремонте и согласовании изменений в квартире.',
                'cta': '👉 Задать вопрос: @Parkhovenko_i_kompaniya_bot'
            }
        }

        self.birthday_templates = [
            "Поздравляем вас с днем рождения! Пусть этот день будет наполнен радостью, теплом близких и приятными сюрпризами. Желаем крепкого здоровья, душевного равновесия и исполнения самых заветных желаний.",
            "С днем рождения! Пусть этот особенный день принесет вам море улыбок, тепла от родных и друзей, а также исполнение всех мечтаний. Желаем здоровья, счастья и благополучия на каждый день.",
            "Поздравляем с днем рождения! Пусть этот день будет ярким и незабываемым, наполненным любовью близких и приятными моментами. Желаем крепкого здоровья, семейного тепла и достижения всех поставленных целей.",
        ]

    async def _call_yandex_gpt(self, user_prompt: str) -> str:
        """Асинхронный вызов LLM API через aiohttp"""
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
            "completionOptions": {"stream": False, "temperature": 0.7, "maxTokens": 1000},
            "messages": [
                {"role": "system", "text": system_prompt},
                {"role": "user", "text": user_prompt}
            ]
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.endpoint, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        logger.error(f"GPT API error: {response.status}")
                        return ""
                    
                    data = await response.json()
                    text = data['result']['alternatives'][0]['message']['text']
                    
                    if not text or len(text.strip()) < 10:
                        logger.warning("GPT returned empty response")
                        return ""
                    
                    return text
        except aiohttp.ClientError as e:
            logger.error(f"aiohttp error in GPT call: {e}")
            return ""
        except Exception as e:
            logger.error(f"Error in GPT call: {e}")
            return ""

    def _build_prompt(self, post_type: str, theme: str = None) -> str:
        """Формирует промпт для LLM - полноценный пост 400-500 знаков"""
        season = self._get_season_context()
        theme_note = f"\nУчитывай тему недели: {theme}" if theme else ""

        CTA_TEXT = "👉 Записаться на консультацию: @Parkhovenko_i_kompaniya_bot"

        prompts = {
            'экспертиза': f"""Создай экспертный пост для Telegram-канала по перепланировкам квартир в Москве.

Контекст сезона: {season}{theme_note}

СТРУКТУРА ПОСТА (обязательно):
1) 💡 Цепляющий заголовок с эмодзи
2) 📝 2-3 абзаца сути (400-500 знаков)
3) 🎯 Призыв к действию в конце

Пример: "😱 Штраф 2000₽ за снос стены! Юрист объясняет, как избежать"
"Собственники часто не знают, что..."
"👉 Записаться: @Bot"

Сделай экспертно, с конкретным примером! {CTA_TEXT}""",
            'живой': f"""Создай «живой» пост для Telegram-канала по перепланировкам.

Контекст сезона: {season}{theme_note}

СТРУКТУРА ПОСТА (обязательно):
1) 🎬 Сезонный зацеп или тренд
2) 💬 Связка с темой перепланировки
3) 👉 CTA к боту

Пример: "🌸 Весна = ремонтный сезон!"
"Люди снимают квартиры и сразу планируют..."
{CTA_TEXT}""",
            'новость': f"""Создай новостной пост для Telegram-канала по перепланировкам.

Требования:
- Что изменилось в законах
- Как это затронет собственников
- Что делать

СТРУКТУРА:
1) 📢 Заголовок новости
2) 💡 Суть изменения в 2-3 предложениях
3) 👉 CTA

{CTA_TEXT}""",
            'поздравление': f"""Напиши короткое искреннее поздравление с днём рождения.

Требования:
- 60-100 слов
- Тёплые пожелания
- Эмодзи
- БЕЗ продаж и услуг

Формат:
🎂 [Имя]

[Поздравление 2-3 строки]""",
            'приветствие': f"""Создай приветственное сообщение для нового подписчика.

Требования:
- 80-120 слов
- Кратко о канале
- 1-2 примера тем
- CTA к боту

Формат:
👋 [Имя]

[Текст] {CTA_TEXT}"""
        }

        return prompts.get(post_type, prompts.get('экспертиза', ''))

    def _get_season_context(self) -> str:
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

    def _parse_response(self, text: str):
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

    def _get_fallback(self, post_type: str) -> dict:
        """Возвращает fallback шаблон"""
        fallback = self.fallback_templates.get(post_type, self.fallback_templates['экспертиза'])
        return fallback.copy()

    async def generate_posts(self, count: int = 7, post_types: dict = None, theme: str = None, channel: str = 'terion'):
        """Асинхронно генерирует N постов (лимит до 500 знаков)"""
        if post_types is None:
            post_types = {'экспертиза': count - 1, 'живой': 1}

        posts = []
        start_date = datetime.now() + timedelta(days=1)
        start_date = start_date.replace(hour=10, minute=0, second=0)

        for post_type, num in post_types.items():
            for i in range(num):
                prompt = self._build_prompt(post_type, theme)
                text = await self._call_yandex_gpt(prompt)
                
                # Fallback при ошибке
                if not text:
                    fallback = self._get_fallback(post_type)
                    title = fallback['title']
                    body = fallback['body'][:500]  # Лимит 500 знаков
                    cta = fallback['cta']
                else:
                    title, body, cta = self._parse_response(text)
                    # Обрезаем до 500 знаков
                    body = body[:500]

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

    def build_image_prompt(self, post: dict) -> str:
        """Генерирует промпт для Flux"""
        post_type = post.get('type')
        channel = post.get('channel', 'terion')

        terion_prompts = {
            'экспертиза': "architectural visualization, blueprints, professional office, legal papers, corporate style, clean minimalist design, 4k resolution, no people",
            'живой': "modern apartment renovation Moscow, interior design, realistic lighting, open space kitchen living room, minimalist corporate style, 4k resolution",
            'новость': "Moscow construction news, architectural update, city building context, professional corporate style, technical aesthetic, 4k resolution",
            'поздравление': "elegant celebration background, warm golden lighting, festive decoration soft colors, cozy atmosphere, professional style, 4k resolution",
            'приветствие': "professional consultation office, modern workspace, clean minimalist design, welcoming business atmosphere, 4k resolution"
        }

        dom_grand_prompts = {
            'экспертиза': "construction site, building process, house renovation, technical details, blueprints on site, professional builder aesthetic, construction materials, 4k resolution",
            'живой': "country house construction, rural property, building site progress, realistic working environment, construction team, modern rural architecture, 4k resolution",
            'новость': "building news rural, construction update, house project progress, technical construction photography, professional site documentation, 4k resolution",
            'поздравление': "warm country house celebration, rural home atmosphere, festive construction site decoration, cozy home feeling, professional style, 4k resolution",
            'приветствие': "construction company office, technical supervision workspace, building plans, professional builder setting, welcoming atmosphere, 4k resolution"
        }

        prompts = dom_grand_prompts if channel == 'dom_grand' else terion_prompts
        base_prompt = prompts.get(post_type, prompts.get('экспертиза', ''))

        if post.get('theme'):
            base_prompt += f", theme: {post['theme']}"

        return base_prompt

    async def generate_post_with_image(self, post_type: str, theme: str = None, channel: str = 'terion') -> dict:
        """Асинхронно генерирует пост и изображение"""
        prompt = self._build_prompt(post_type, theme)
        text = await self._call_yandex_gpt(prompt)
        
        # Fallback при ошибке
        if not text:
            fallback = self._get_fallback(post_type)
            title = fallback['title']
            body = fallback['body'][:500]
            cta = fallback['cta']
        else:
            title, body, cta = self._parse_response(text)
            body = body[:500]

        post_dict = {'type': post_type, 'theme': theme, 'channel': channel}
        image_prompt = self.build_image_prompt(post_dict)
        
        # Генерируем изображение
        try:
            from image_gen import generate
            image_url = await generate(image_prompt) if callable(generate) else None
        except ImportError:
            logger.error("Модуль image_gen не найден")
            image_url = None
        except Exception as e:
            logger.error(f"Ошибка генерации изображения: {e}")
            image_url = None

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

    async def generate_greeting_post(self, person_name: str = None, date: str = None, occasion: str = 'день рождения') -> dict:
        """Асинхронно генерирует поздравление"""
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

        text = await self._call_yandex_gpt(prompt)

        # Проверяем на продажи
        banned = ["ремонт", "перепланиров", "услуг", "консультац", "бот", "скидк"]
        if any(word in text.lower() for word in banned):
            text = random.choice(self.birthday_templates)
            text = f"🎂 {display_name}\n\n{text}"

        title, body, cta = self._parse_response(text)
        return {'type': 'поздравление', 'title': title, 'body': body, 'cta': cta}

    async def generate_welcome_post(self, person_name: str = None) -> dict:
        """Асинхронно генерирует приветствие"""
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

        text = await self._call_yandex_gpt(prompt)
        
        # Fallback при ошибке
        if not text:
            fallback = self._get_fallback('приветствие')
            title = fallback['title']
            body = fallback['body'][:500]
            cta = fallback['cta']
        else:
            title, body, cta = self._parse_response(text)
            body = body[:500]

        return {'type': 'приветствие', 'title': title, 'body': body, 'cta': cta}

    async def generate_image(self, prompt: str) -> Optional[str]:
        """Генерирует изображение через Router AI (Flux)"""
        import aiohttp
        
        api_key = os.getenv("ROUTER_AI_IMAGE_KEY", "").strip()
        model = os.getenv("FLUX_MODEL", "flux-1-dev")
        url = os.getenv("ROUTER_IMAGE_URL", "https://api.router.ai/v1/image_generation")
        
        if not api_key:
            logger.error("ROUTER_AI_IMAGE_KEY не настроен")
            return None
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "prompt": prompt,
            "width": 1024,
            "height": 1024,
            "num_images": 1
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status != 200:
                        logger.error(f"Image API error: {resp.status}")
                        return None
                    
                    result = await resp.json()
                    
                    if result.get("data") and len(result["data"]) > 0:
                        image_url = result["data"][0].get("url") or result["data"][0].get("image_url")
                        if image_url:
                            logger.info(f"Image generated: {image_url}")
                            return image_url
                    
                    return None
        except Exception as e:
            logger.error(f"Image generation error: {e}")
            return None
