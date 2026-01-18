import asyncio
import logging
from datetime import datetime
from database import db

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutoPoster:
    """Класс для автоматической публикации контента в канал"""

    def __init__(self, bot, channel_id: str):
        """
        Инициализация AutoPoster

        Args:
            bot: Экземпляр телеграм-бота
            channel_id: ID канала для публикации
        """
        self.bot = bot
        self.channel_id = channel_id

    async def check_and_publish(self):
        """Проверяет и публикует готовые посты"""
        try:
            # Получаем посты, готовые к публикации
            posts = await db.get_posts_to_publish()

            if not posts:
                logger.info("Нет постов для публикации")
                return

            logger.info(f"Найдено {len(posts)} постов для публикации")

            for post in posts:
                try:
                    # Форматируем пост
                    formatted_post = self._format_post(post)

                    # Отправляем в канал
                    await self.bot.send_message(
                        chat_id=self.channel_id,
                        text=formatted_post,
                        parse_mode='Markdown'
                    )

                    # Отмечаем как опубликованный
                    await db.mark_as_published(post['id'])

                    logger.info(f"✅ Пост #{post['id']} опубликован в канал")

                    # Логируем публикацию в THREAD_ID_LOGS группы
                    import os
                    LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "0"))
                    THREAD_ID_LOGS = int(os.getenv("THREAD_ID_LOGS", "88"))

                    log_text = f"📤 Пост опубликован в канал\nID: {post['id']}\nТип: {post['post_type']}\nЗаголовок: {post.get('title', 'Без заголовка')}\nВремя: {datetime.now()}"
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

    def _format_post(self, post) -> str:
        """
        Форматирует пост для Telegram

        Args:
            post: Словарь с данными поста

        Returns:
            str: Отформатированный текст поста
        """
        title = post.get('title', '').strip()
        body = post.get('body', '').strip()
        cta = post.get('cta', '').strip()

        # Формируем текст
        parts = []

        if title:
            parts.append(f"*{title}*")
            parts.append("")  # Пустая строка

        if body:
            parts.append(body)
            parts.append("")  # Пустая строка

        if cta:
            parts.append(f"*{cta}*")

        return "\n".join(parts).strip()


async def run_auto_poster(bot, channel_id: str):
    """
    Запускает автоматическую публикацию в фоне

    Args:
        bot: Экземпляр телеграм-бота
        channel_id: ID канала для публикации
    """
    poster = AutoPoster(bot, channel_id)
    logger.info("🚀 AutoPoster запущен. Проверка каждые 10 минут.")

    while True:
        try:
            await poster.check_and_publish()

        except Exception as e:
            logger.error(f"❌ Критическая ошибка в run_auto_poster: {e}")

        # Ждём 10 минут (600 секунд)
        await asyncio.sleep(600)
