import asyncio
import logging
import os
from datetime import datetime
from html import escape
from database import db
from image_agent import ImageAgent

def safe_html(text: str) -> str:
    """Экранирует HTML-спецсимволы для безопасной отправки с parse_mode='HTML'"""
    return escape(text)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONTENT_CHANNEL_ID = int(os.getenv("CONTENT_CHANNEL_ID", 0))

YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
FOLDER_ID = os.getenv("FOLDER_ID")

if not YANDEX_API_KEY or not FOLDER_ID:
    raise RuntimeError("YANDEX_API_KEY and FOLDER_ID must be set in environment")


class AutoPoster:
    """Класс для автоматической публикации контента в канал"""

    def __init__(self, bot):
        """
        Инициализация AutoPoster

        Args:
            bot: Экземпляр телеграм-бота
        """
        self.bot = bot
        self.channel_id = CONTENT_CHANNEL_ID

    async def _check_and_publish_holidays(self):
        """
        Проверяет и публикует праздничные поздравления (один раз в сутки)
        """
        try:
            # Получаем сегодняшние праздники
            holidays = await db.get_today_holidays()

            if not holidays:
                logger.info("Сегодня нет праздников для публикации")
                return  # Нет праздников сегодня

            # Проверяем, не публиковали ли мы уже сегодня поздравления
            # Используем файл как простой механизм защиты от дублирования
            today_str = datetime.now().strftime("%Y-%m-%d")
            holiday_flag_file = f"holiday_published_{today_str}.flag"

            if os.path.exists(holiday_flag_file):
                logger.info("Праздничные поздравления уже опубликованы сегодня")
                return

            logger.info(f"Найдено {len(holidays)} праздников на сегодня")

            for holiday in holidays:
                try:
                    # Используем message_template напрямую (без GPT)
                    message_text = holiday['message_template']

                    # Добавляем название праздника в начало
                    full_message = f"🎉 <b>{holiday['name']}</b>\n\n{message_text}"

                    # Публикуем в канал
                    logger.info(f"Публикуем поздравление с {holiday['name']}")
                    await self.bot.send_message(
                        chat_id=CONTENT_CHANNEL_ID,
                        text=full_message,
                        parse_mode='HTML'
                    )

                    logger.info(f"✅ Поздравление с {holiday['name']} опубликовано в канал {CONTENT_CHANNEL_ID}")

                    # Логируем публикацию
                    import os
                    LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "0"))
                    THREAD_ID_LOGS = int(os.getenv("THREAD_ID_LOGS", "88"))

                    log_text = f"🎉 Праздничное поздравление\nНазвание: {holiday['name']}\nДата: {holiday['date']}\nВремя: {datetime.now()}"
                    try:
                        await self.bot.send_message(
                            chat_id=LEADS_GROUP_CHAT_ID,
                            text=log_text,
                            message_thread_id=THREAD_ID_LOGS
                        )
                    except Exception as e:
                        logger.error(f"Failed to send holiday log: {e}")

                    # Небольшая пауза между поздравлениями
                    await asyncio.sleep(1)

                except Exception as e:
                    logger.error(f"❌ Ошибка публикации поздравления {holiday['name']}: {e}")
                    continue

            # Создаем флаг-файл, чтобы не публиковать повторно сегодня
            try:
                with open(holiday_flag_file, 'w') as f:
                    f.write(today_str)
                logger.info("Создан флаг-файл для предотвращения повторной публикации")
            except Exception as e:
                logger.error(f"Не удалось создать флаг-файл: {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка в _check_and_publish_holidays: {e}")

    async def check_and_publish(self):
        """Проверяет и публикует готовые посты"""
        try:
            # Сначала проверяем праздники
            await self._check_and_publish_holidays()

            # Получаем посты, готовые к публикации
            posts = await db.get_posts_to_publish()

            if not posts:
                logger.info("Нет постов для публикации")
                return

            logger.info(f"[AutoPoster] Found {len(posts)} posts to publish")

            # Генерируем изображения для постов с промптами
            for post in posts:
                if post.get('image_prompt') and not post.get('image_url'):
                    logger.info(f"[AutoPoster] Generating image for post {post['id']} (type={post.get('type')}, prompt={post.get('image_prompt')!r})")
                    agent = ImageAgent()
                    image_url = agent.generate_image(post['image_prompt'])
                    if image_url:
                        await db.update_content_plan_entry(post_id=post['id'], image_url=image_url)
                        post['image_url'] = image_url
                        logger.info(f"✅ Сгенерировано изображение для поста #{post['id']}")
                    else:
                        logger.warning(f"[AutoPoster] Image generation returned no URL for post {post['id']}")

            for post in posts:
                try:
                    # Если текст поста не заполнен, генерируем его
                    if not post.get('body') or not post.get('body').strip():
                        logger.info(f"Генерируем текст для поста #{post['id']} типа '{post.get('type', 'unknown')}'")
                        await self._generate_missing_text(post)

                    # Форматируем пост
                    formatted_post = self._format_post(post)

                    # Отправляем в канал
                    logger.info(f"[AutoPoster] Publishing post {post['id']} (type={post.get('type')}, has_image={bool(post.get('image_url'))})")
                    if post.get('image_url'):
                        await self.bot.send_photo(chat_id=CONTENT_CHANNEL_ID, photo=post['image_url'], caption=formatted_post, parse_mode='HTML')
                    else:
                        await self.bot.send_message(chat_id=CONTENT_CHANNEL_ID, text=formatted_post, parse_mode='HTML')

                    # Отмечаем как опубликованный
                    await db.mark_as_published(post['id'])

                    logger.info(f"[AutoPoster] Post {post['id']} published successfully")

                    # Логируем публикацию в THREAD_ID_LOGS группы
                    import os
                    LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "0"))
                    THREAD_ID_LOGS = int(os.getenv("THREAD_ID_LOGS", "88"))

                    log_text = f"📤 Пост опубликован в канал\nID: {post['id']}\nТип: {post['type']}\nЗаголовок: {post.get('title', 'Без заголовка')}\nВремя: {datetime.now()}"
                    try:
                        await self.bot.send_message(
                            chat_id=LEADS_GROUP_CHAT_ID,
                            text=log_text,
                            message_thread_id=THREAD_ID_LOGS
                        )
                    except Exception as e:
                        logger.error(f"Failed to send publication log: {e}")

                    # Небольшая пауза между постами
                    await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"❌ Ошибка публикации поста #{post['id']}: {e}")

                    # Логируем ошибку публикации
                    import os
                    LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "0"))
                    THREAD_ID_LOGS = int(os.getenv("THREAD_ID_LOGS", "88"))

                    error_log = f"❌ ОШИБКА публикации\nID: {post['id']}\nДетали: {str(e)}\nВремя: {datetime.now()}"
                    try:
                        await self.bot.send_message(
                            chat_id=LEADS_GROUP_CHAT_ID,
                            text=error_log,
                            message_thread_id=THREAD_ID_LOGS
                        )
                    except:
                        pass

                    continue

        except Exception as e:
            logger.error(f"❌ Ошибка в check_and_publish: {e}")

    async def _generate_missing_text(self, post):
        """
        Генерирует текст поста, если он отсутствует

        Args:
            post: Словарь с данными поста (будет модифицирован)
        """
        try:
            logger.info(f"[AutoPoster] Generating missing text for post {post['id']} (type={post.get('type')})")

            from content_agent import ContentAgent

            agent = ContentAgent(
                api_key=YANDEX_API_KEY,
                model_uri=f"gpt://{FOLDER_ID}/yandexgpt/latest"
            )
            plan_item = {
                'type': post.get('type', 'fact'),
                'theme': post.get('theme', None)  # Если есть поле theme
            }

            # Генерируем текст
            text_data = agent.generate_post_text(plan_item)

            # Обновляем пост в базе данных
            await db.update_content_plan_entry(
                post_id=post['id'],
                title=text_data.get('title'),
                body=text_data.get('body'),
                cta=text_data.get('cta')
            )

            # Обновляем локальный объект поста
            post.update(text_data)

            logger.info(f"[AutoPoster] Missing text generated and saved for post {post['id']}")

        except Exception as e:
            logger.error(f"❌ Ошибка генерации текста для поста #{post['id']}: {e}")

    def _format_post(self, post) -> str:
        """
        Форматирует пост для Telegram

        Args:
            post: Словарь с данными поста

        Returns:
            str: Отформатированный текст поста
        """
        title = escape(post.get('title', '').strip())
        body = escape(post.get('body', '').strip())
        cta = escape(post.get('cta', '').strip())

        # Формируем текст
        parts = []

        if title:
            parts.append(f"<b>{title}</b>")
            parts.append("")  # Пустая строка

        if body:
            parts.append(body)
            parts.append("")  # Пустая строка

        if cta:
            parts.append(f"<b>{cta}</b>")

        return "\n".join(parts).strip()


async def run_auto_poster(bot):
    """
    Запускает автоматическую публикацию в фоне

    Args:
        bot: Экземпляр телеграм-бота
    """
    poster = AutoPoster(bot)
    logger.info("🚀 AutoPoster запущен. Проверка каждые 10 минут.")

    while True:
        try:
            await poster.check_and_publish()

        except Exception as e:
            logger.error(f"❌ Критическая ошибка в run_auto_poster: {e}")

        # Ждём 10 минут (600 секунд)
        await asyncio.sleep(600)
