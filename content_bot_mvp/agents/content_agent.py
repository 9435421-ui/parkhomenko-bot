 ебе еще import requests
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
        self.endpoint = os.getenv("ROUTER_AI_ENDPOINT", "https://routerai.ru/api/v1/chat/completions")
        
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

    def generate_welcome_post(self, person_name: str | None = None):
        """
        Генерирует приветственное сообщение-визитку для потенциального клиента.

        Args:
            person_name: Имя человека или None

        Returns:
            dict: {'title': str, 'body': str, 'cta': str, 'type': 'приветствие'}
        """
        display_name = person_name if person_name else "новый подписчик"

        prompt = f"""
Создай приветственное сообщение для Telegram-канала по перепланировкам.

Адресат: {display_name}

Требования:
- 80–120 слов
- Кратко представить канал и пользу: помощь с вопросами перепланировки, рисками, узакониванием
- 1–2 простых примера ситуаций, когда к нам можно обратиться (перенос стен, объединение кухни и комнаты, перепланировка с мокрыми зонами)
- Один аккуратный CTA к боту @ТЕРИОН_i_kompaniya_bot
- Спокойный, дружелюбный тон

Формат ответа:
👋 {display_name}

[Текст приветствия 2–3 абзаца с CTA в конце]
"""
        text = self._call_yandex_gpt(prompt, mode="default")  # обычный продающий режим
        title, body, cta = self._parse_response(text)

return {
            'type': 'приветствие',
            'title': title,
            'body': body,
            'cta': cta
        }

    def generate_greeting_post(self, person_name, date, occasion='день рождения'):
        """
        Генерирует персональный поздравительный пост

        Args:
            person_name: Имя человека (может быть пустым)
            date: Дата в формате DD.MM или DD.MM.YYYY
            occasion: Повод для поздравления ('день рождения', 'Новый год', etc.)

        Returns:
            dict: {'title': str, 'body': str, 'cta': str, 'type': 'поздравление'}
        """
        display_name = person_name if person_name else "наш подписчик"

        prompt = f"""
Создай короткое искреннее поздравление для личного сообщения в Telegram.

Повод: {occasion}
Имя: {display_name}
Дата: {date}

Требования:
- Тёплое персональное поздравление (60–100 слов)
- Пожелания здоровья, радости, душевного комфорта, уюта дома
- Простой дружелюбный язык, без высокопарного канцелярита
- Строго запрещено упоминать услуги, ремонт, перепланировку, консультации, ботов, компании, акции, скидки и любые продажи.
- Не добавляй CTA, ссылки, хэштеги, GIF и призывы что-то заказать или узнать.

Формат ответа:
🎂 {display_name}

[Поздравление с пожеланиями]
"""

        text = self._call_yandex_gpt(prompt, mode="greeting")
        text = self._sanitize_greeting(text)

        # Для поздравления title можно не использовать, всё в body
        title = ""
        body = text.strip()
        cta = ""  # никаких CTA в поздравлении

        return {
            'type': 'поздравление',
            'title': title,
            'body': body,
            'cta': cta
        }

    def build_image_prompt(self, post: dict) -> str | None:
        """
        system_prompt = """Ты — ведущий контент-стратег и эксперт по продажам компании TERION.
Твоя специализация: легализация перепланировок в Москве и МО.

Твоя задача: создавать виральный и экспертный контент, который убеждает владельцев недвижимости в необходимости профессионального согласования.
Стиль: уверенный, экспертный, местами провокационный (через боли клиентов: штрафы, суды), но всегда конструктивный.

Каждый пост должен вести к действию: переходу в @Parkhovenko_i_kompaniya_bot."""

        is_router = "routerai.ru" in self.endpoint

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}" if is_router else f"Api-Key {self.api_key}",
        }
        if not is_router and self.folder_id:
            headers["x-folder-id"] = self.folder_id

        if is_router:
            payload = {
                "model": os.getenv("ROUTER_AI_CHAT_MODEL", "gpt-4o-mini"),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 1000,
            }
        else:
            payload = {
                "modelUri": f"gpt://{self.folder_id}/yandexgpt/latest",
                "completionOptions": {"stream": False, "temperature": 0.7, "maxTokens": 1000},
                "messages": [
                    {"role": "system", "text": system_prompt},
                    {"role": "user", "text": user_prompt},
                ],
            }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint, headers=headers, json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"GPT API error: {response.status} — {error_text[:200]}")
                        return ""

                    data = await response.json()
                    if is_router:
                        text = data["choices"][0]["message"]["content"]
                    else:
                        text = data["result"]["alternatives"][0]["message"]["text"]

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

    def _build_prompt(self, post_type: str, theme: str = None, platform: str = 'telegram') -> str:
        """Формирует промпт для LLM - полноценный пост 400-500 знаков"""
        season = self._get_season_context()
        theme_note = f"\nУчитывай тему недели: {theme}" if theme else ""

        CTA_TEXT = "👉 Записаться на консультацию: @Parkhovenko_i_kompaniya_bot"

        # Платформенные модификаторы
        if platform == 'max':
            # Для Max.ru - развернуто с подзаголовками и списками
            vk_hashtags = ""
            max_instructions = """
📝 ПИШИ РАЗВЕРНУТО:
- Используй подзаголовки (##)
- Используй маркированные списки (- или *)
- Объем: 500-800 знаков
- Структурируй информацию логически"""
        elif platform == 'vk':
            # Для ВК - с хештегами
            vk_hashtags = "\n\nДОБАВЬ 3-5 релевантных хештегов в конце: #перепланировка #ремонт #недвижимость"
            max_instructions = ""
        else:
            # Telegram - стандарт
            vk_hashtags = ""
            max_instructions = ""

        expert_block = self._load_expert_cases()
        prompts = {
            'экспертиза': f"""Создай экспертный пост для Telegram-канала по перепланировкам квартир в Москве.

Реальные кейсы и термины (ОБЯЗАТЕЛЬНО использовать по смыслу): {expert_block}

Контекст сезона: {season}{theme_note}{max_instructions}

СТРУКТУРА ПОСТА (обязательно):
1) 💡 Цепляющий заголовок с эмодзи
2) 📝 2-3 абзаца сути (400-500 знаков). Используй: МЖИ, несущие стены, трассировка или акты скрытых работ
3) 🎯 Призыв к действию в конце

ЗАПРЕЩЕНО: общие фразы без терминов, «уникальный дизайн», «за 3 дня». Сделай с конкретным примером из кейсов! {CTA_TEXT}{vk_hashtags}""",
            'живой': f"""Создай «живой» пост для Telegram-канала по перепланировкам.

Контекст сезона: {season}{theme_note}{max_instructions}

СТРУКТУРА ПОСТА (обязательно):
1) 🎬 Сезонный зацеп или тренд
2) 💬 Связка с темой перепланировки
3) 👉 CTA к боту

Пример: "🌸 Весна = ремонтный сезон!"
"Люди снимают квартиры и сразу планируют..."
{CTA_TEXT}{vk_hashtags}""",
            'новость': f"""Создай новостной пост для Telegram-канала по перепланировкам.

{theme_note}{max_instructions}

Требования:
- Что изменилось в законах
- Как это затронет собственников
- Что делать

СТРУКТУРА:
1) 📢 Заголовок новости
2) 💡 Суть изменения в 2-3 предложениях
3) 👉 CTA

{CTA_TEXT}{vk_hashtags}""",
            'поздравление': f"""Напиши короткое искреннее поздравление с днём рождения.

👉 [CTA с призывом к действию]
""",
            'живой': f"""
Создай «живой» пост для Telegram-канала по перепланировкам.

Контекст сезона: {season}{theme_note}

Требования:
- Привязка к текущим событиям (погода, отключения ЖКХ, сезонные проблемы жильцов)
- 150–250 слов, по-человечески, с личной ноткой
- Мягкий переход к теме перепланировок и рисков
- CTA к боту @Parkhovenko_i_kompaniya_bot

Формат ответа:
[Сезонный зацеп или наблюдение]

[Связка с темой перепланировок]

👉 [CTA]
""",
            'новость': f"""
Создай новостной пост для Telegram-канала по перепланировкам.

Требования:
- Объявление об изменении норм, новом разъяснении или важном кейсе
- 120–200 слов, кратко и чётко
- Что изменилось и чем это чревато для жильцов
- CTA к боту @Parkhovenko_i_kompaniya_bot для разбора конкретной ситуации{theme_note}

Формат ответа:
[Новость простыми словами]

[Что это значит для жильцов]

👉 [CTA]
""",
            'поздравление': f"""
Напиши короткое искреннее поздравление с днём рождения.

Кого поздравляем: {theme_note or 'друг'}

Требования:
- 60-100 слов
- Тёплые пожелания
- Эмодзи
- БЕЗ продаж и услуг

Формат:
🎂 [Имя]

[Поздравление 2-3 строки]{vk_hashtags}""",
            'приветствие': f"""Создай приветственное сообщение для нового подписчика.

{max_instructions}

Требования:
- 80-120 слов
- Кратко о канале
- 1-2 примера тем
- CTA к боту

Формат:
👋 [Имя]

[Текст] {CTA_TEXT}{vk_hashtags}"""
        }

        return prompts.get(post_type, prompts.get('экспертиза', ''))

    def _load_expert_cases(self) -> str:
        """Загружает expert_cases.txt для вставки в промпты (термины МЖИ, несущие стены, трассировка, акты скрытых работ)."""
        path = os.path.join(os.path.dirname(__file__), "templates", "content", "expert_cases.txt")
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return f.read().strip()[:2000]
        except Exception as e:
            logger.warning(f"expert_cases.txt: {e}")
        return "МЖИ, несущие стены, трассировка, акты скрытых работ. Избегай общих фраз."

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

        no_text_suffix = " No text, no words, no letters, no captions — image only."
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
        return base_prompt + no_text_suffix

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
        """Асинхронно генерирует поздравление от лица главы компании TERION — статусно и тепло."""
        display_name = person_name if person_name else "друзья"
        prompt = f"""Создай поздравление ОТ ЛИЦА ГЛАВЫ КОМПАНИИ TERION (руководитель бюро перепланировок).

Повод: {occasion}
Обращение: к {display_name}
Дата: {date}

Требования:
- Текст от первого лица как глава TERION: «От имени команды TERION желаю…», «Поздравляю от всей души…»
- Статусный, тёплый, профессиональный тон. 60-100 слов.
- БЕЗ продаж, скидок и призывов к услугам. Только пожелания.

Формат:
🎉 [Краткое обращение от главы TERION]

[Поздравление от лица компании]"""

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

    async def _get_max_subsite_id(self) -> Optional[str]:
        """Получает ID сайта из Max.ru API"""
        import aiohttp
        
        device_token = os.getenv("MAX_DEVICE_TOKEN", "").strip()
        url = "https://api.max.ru/v1.9/subsite/me"
        
        if not device_token:
            logger.error("MAX_DEVICE_TOKEN не настроен")
            return None
        
        headers = {
            "X-Device-Token": device_token,
            "Content-Type": "application/json"
        }
        
        try:
            # Игнорируем SSL проверку
            connector = aiohttp.TCPConnector(verify_ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status != 200:
                        logger.error(f"Max API error: {resp.status}")
                        return None
                    
                    result = await resp.json()
                    subsite_id = result.get("id") or result.get("subsite_id")
                    
                    if subsite_id:
                        logger.info(f"Max.ru subsite_id: {subsite_id}")
                        print(f"🔗 Max.ru subsite_id: {subsite_id}")
                        return subsite_id
                    
                    logger.warning(f"Max API response: {result}")
                    return None
        except Exception as e:
            logger.error(f"Max API error: {e}")
            return None

    async def post_to_max(self, post_id: int, subsite_id: str = None) -> bool:
        """Публикует пост в Max.ru"""
        import aiohttp
        
        if not subsite_id:
            subsite_id = await self._get_max_subsite_id()
        
        if not subsite_id:
            logger.error("Не удалось получить subsite_id для Max.ru")
            return False
        
        device_token = os.getenv("MAX_DEVICE_TOKEN", "").strip()
        url = f"https://api.max.ru/v1.9/subsite/{subsite_id}/content"
        
        if not device_token:
            logger.error("MAX_DEVICE_TOKEN не настроен")
            return False
        
        headers = {
            "X-Device-Token": device_token,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {device_token}",
        }
        
        # Получаем пост из БД
        from database import db
        post = await db.get_content_post(post_id)
        
        if not post:
            logger.error(f"Пост {post_id} не найден")
            return False
        
        import re
        body_raw = post.get("body", "")
        body_plain = re.sub(r"<[^>]+>", "", body_raw) if body_raw else ""
        body_plain = re.sub(r"&nbsp;", " ", body_plain).strip()
        
        payload = {
            "title": (post.get("title") or "")[:200],
            "body": body_plain[:5000] or body_raw[:5000],
            "type": "post"
        }
        
        try:
            connector = aiohttp.TCPConnector(verify_ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status == 200:
                        logger.info(f"Пост {post_id} опубликован в Max.ru")
                        return True
                    else:
                        error_text = await resp.text()
                        logger.error(f"Max publish error {resp.status}: {error_text}")
                        return False
        except Exception as e:
            logger.error(f"Max publish error: {e}")
            return False
