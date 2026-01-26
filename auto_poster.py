import asyncio
import logging
import os
from datetime import datetime
from html import escape
from database import db

def safe_html(text: str) -> str:
    """Экранирует HTML-спецсимволы для безопасной отправки с parse_mode='HTML'"""
    return escape(text)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONTENT_CHANNEL_ID = int(os.getenv("CONTENT_CHANNEL_ID"))


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

    async def check_and_publish(self):
        """Проверяет и публикует готовые посты"""
        try:
            # Получаем посты, готовые к публикации
            posts = db.get_posts_to_publish()

            if not posts:
                logger.info("Нет постов для публикации")
                return

            logger.info(f"Найдено {len(posts)} постов для публикации")

            for post in posts:
                try:
                    # Форматируем пост
                    formatted_post = self._format_post(post)
                    image_url = post.get('image_url')

                    # Отправляем в канал
                    logging.info(f"Publishing post {post['id']}: len={len(formatted_post)}, has_image={bool(image_url)}")

                    if image_url:
                        try:
                            # Если есть изображение, отправляем как фото с подписью
                            if os.path.exists(image_url):
                                with open(image_url, 'rb') as photo:
                                    self.bot.send_photo(
                                        chat_id=CONTENT_CHANNEL_ID,
                                        photo=photo,
                                        caption=formatted_post[:1024] # Лимит подписи в TG
                                    )
                            else:
                                # Если это URL или file_id
                                self.bot.send_photo(
                                    chat_id=CONTENT_CHANNEL_ID,
                                    photo=image_url,
                                    caption=formatted_post[:1024]
                                )
                        except Exception as e:
                            logger.error(f"Ошибка отправки фото для поста #{post['id']}: {e}. Отправляю только текст.")
                            self.bot.send_message(chat_id=CONTENT_CHANNEL_ID, text=formatted_post)
                    else:
                        # Если нет изображения, отправляем просто текст
                        self.bot.send_message(chat_id=CONTENT_CHANNEL_ID, text=formatted_post)

                    # Отмечаем как опубликованный
                    db.mark_as_published(post['id'])

                    logger.info(f"✅ Пост #{post['id']} опубликован в канал")

                    # Логируем публикацию в THREAD_ID_LOGS группы
                    import os
                    LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "0"))
                    THREAD_ID_LOGS = int(os.getenv("THREAD_ID_LOGS", "88"))

                    log_text = f"📤 Пост опубликован в канал\nID: {post['id']}\nТип: {post['type']}\nЗаголовок: {post.get('title', 'Без заголовка')}\nВремя: {datetime.now()}"
                    try:
                        self.bot.send_message(
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
                        self.bot.send_message(
                            chat_id=LEADS_GROUP_CHAT_ID,
                            text=error_log,
                            message_thread_id=THREAD_ID_LOGS
                        )
                    except:
                        pass

                    continue

        except Exception as e:
            logger.error(f"❌ Ошибка в check_and_publish: {e}")

    async def run_daily_checks(self):
        """Ежедневные проверки: дни рождения, праздники, новости"""
        logger.info("📅 Запуск ежедневных проверок...")

        from content_agent import ContentAgent
        agent = ContentAgent()

        today = datetime.now().strftime("%d.%m")

        # 1. Дни рождения подписчиков
        birthdays = db.get_today_birthdays()
        for sub in birthdays:
            user_id = sub['user_id']
            name = sub['first_name'] or sub['username'] or "наш подписчик"

            # Генерируем поздравление из шаблонов
            congrats = agent.generate_birthday_congrats_template(name, today)

            try:
                self.bot.send_message(user_id, congrats['body'])
                logger.info(f"🎂 Поздравил {name} (ID: {user_id}) с днем рождения")
            except Exception as e:
                logger.error(f"Не удалось поздравить {user_id}: {e}")

        # 2. Мониторинг новостей
        logger.info("🔍 Мониторинг новостей законодательства...")
        news = agent.monitor_legal_news()
        for item in news:
            # Проверяем, нет ли уже такой новости в базе
            db.add_news(item['title'], item['url'])

        # Получаем новые новости и уведомляем админа
        new_news = db.get_unnotified_news()
        if new_news:
            import os
            LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "0"))
            THREAD_ID_LOGS = int(os.getenv("THREAD_ID_LOGS", "88"))

            for item in new_news:
                text = f"🆕 <b>Найдена важная новость:</b>\n\n{safe_html(item['title'])}\n\n🔗 {item['url']}\n\n<i>Предлагаю использовать как инфоповод для поста!</i>"
                try:
                    self.bot.send_message(
                        chat_id=LEADS_GROUP_CHAT_ID,
                        text=text,
                        message_thread_id=THREAD_ID_LOGS,
                        parse_mode='HTML'
                    )
                    db.mark_news_as_notified(item['id'])
                except Exception as e:
                    logger.error(f"Ошибка уведомления админа о новости: {e}")

        # 3. Праздники
        holidays = agent.get_russian_holidays()
        if today in holidays:
            holiday_name = holidays[today]
            import os
            LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "0"))
            THREAD_ID_LOGS = int(os.getenv("THREAD_ID_LOGS", "88"))

            try:
                self.bot.send_message(
                    chat_id=LEADS_GROUP_CHAT_ID,
                    text=f"🇷🇺 <b>Сегодня праздник: {holiday_name}</b>\n\nНе забудьте опубликовать поздравление в канале!",
                    message_thread_id=THREAD_ID_LOGS,
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Ошибка уведомления о празднике: {e}")

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

    last_check_date = None

    while True:
        try:
            # 1. Проверка постов для публикации
            await poster.check_and_publish()

            # 2. Ежедневные проверки (один раз в день)
            today_date = datetime.now().date()
            if last_check_date != today_date:
                await poster.run_daily_checks()
                last_check_date = today_date

        except Exception as e:
            logger.error(f"❌ Критическая ошибка в run_auto_poster: {e}")

        # Ждём 10 минут (600 секунд)
        await asyncio.sleep(600)
