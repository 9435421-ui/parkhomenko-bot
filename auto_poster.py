"""
AutoPoster — модуль автоматической публикации контента.

Функционал:
1. Проверка контент-плана (every 10 min)
2. Генерация изображений (Router AI / Flux)
3. Публикация в Telegram каналы (TERION / ДОМ ГРАНД)
4. Кросс-постинг в VK
"""
import asyncio
import logging
import os
from datetime import datetime
import aiohttp
from database.db import db
from services.publisher import publisher

logger = logging.getLogger(__name__)


class AutoPoster:
    """Автопостинг контента в каналы"""

    def __init__(self, bot):
        self.bot = bot
        publisher.bot = bot
        self.check_interval = 600  # 10 минут

    async def check_and_publish(self):
        """Проверка и публикация готового контента"""
        try:
            posts = await db.get_posts_to_publish()
            if not posts:
                logger.info("📭 Нет постов для публикации")
                return

            logger.info(f"📋 Найдено {len(posts)} постов для публикации")

            for post in posts:
                try:
                    # Определяем канал публикации
                    channel_key = self._determine_channel(post)
                    channel_config = self._get_channel_config(channel_key)

                    # Публикуем
                    success = await self._publish_to_channel(post, channel_config)
                    if success:
                        # Логируем в группу
                        await self._send_publication_log(post, channel_config)
                        await db.mark_as_published(post['id'])
                        logger.info(f"✅ Пост #{post['id']} опубликован в {channel_config['name']}")

                except Exception as e:
                    logger.error(f"❌ Ошибка публикации поста #{post.get('id')}: {e}")
                    continue

        except Exception as e:
            logger.error(f"❌ Ошибка в check_and_publish: {e}")

    def _determine_channel(self, post: dict) -> str:
        """Определяет целевой канал для публикации"""
        channel = post.get('channel', '').lower()
        theme = (post.get('theme') or '').lower()
        title = (post.get('title') or '').lower()
        body = (post.get('body') or '').lower()

        # Ключевые слова для ДОМ ГРАНД
        dom_grand_keywords = [
            'загород', 'дом', 'строительство', 'коттедж', 'технадзор',
            'house', 'construction', 'rural', 'cottage'
        ]

        # Проверяем channel явно
        if channel == 'dom_grand':
            return 'dom_grand'

        # Проверяем theme
        for keyword in dom_grand_keywords:
            if keyword in theme:
                return 'dom_grand'

        # Проверяем title и body
        for keyword in dom_grand_keywords:
            if keyword in title or keyword in body:
                return 'dom_grand'

        # По умолчанию — TERION
        return 'terion'

    def _get_channel_config(self, channel_key: str) -> dict:
        """Получает конфигурацию канала из config.py"""
        # ── ИСПРАВЛЕНИЕ: Используем config.py вместо os.getenv ───────────────────────
        from config import CHANNEL_ID_TERION, CHANNEL_ID_DOM_GRAD, CHANNEL_NAMES
        
        configs = {
            'terion': {
                'name': CHANNEL_NAMES.get('terion', 'TERION'),
                'chat_id': CHANNEL_ID_TERION
            },
            'dom_grand': {
                'name': CHANNEL_NAMES.get('dom_grand', 'ДОМ ГРАНД'),
                'chat_id': CHANNEL_ID_DOM_GRAD
            }
        }
        return configs.get(channel_key, configs['terion'])

    async def _publish_to_channel(self, post: dict, channel_config: dict) -> bool:
        """Публикует пост через Publisher в целевой канал (TERION или ДОМ ГРАНД)."""
        try:
            text = self._format_post_text(post)
            title = post.get("title", "") or ""
            image_url = post.get("image_url")
            image_bytes: bytes | None = None

            # Скачиваем изображение по URL, если оно есть
            if image_url and image_url.startswith("http"):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            image_url, timeout=aiohttp.ClientTimeout(total=30)
                        ) as resp:
                            if resp.status == 200:
                                image_bytes = await resp.read()
                                logger.info(
                                    f"✅ Изображение скачано ({len(image_bytes)} байт)"
                                )
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось скачать изображение {image_url}: {e}")

            # ── ИСПРАВЛЕНИЕ: Публикуем в целевой канал, а не во все ──────────────────
            channel_id = channel_config['chat_id']
            success = await publisher.publish_to_telegram(channel_id, text, image_bytes)
            
            if success:
                logger.info(f"✅ Пост опубликован в {channel_config['name']} (ID: {channel_id})")
            
            return success

        except Exception as e:
            logger.error(f"❌ Ошибка публикации: {e}")
            return False

    def _format_post_text(self, post: dict) -> str:
        """Форматирует текст поста"""
        title = post.get('title', '') or ''
        body = post.get('body', '') or ''
        cta = post.get('cta', '') or ''

        parts = []
        if title:
            parts.append(f"<b>{title}</b>")
        if body:
            parts.append(body)
        if cta:
            parts.append(cta)

        return "\n\n".join(parts)

    async def _send_publication_log(self, post: dict, channel_config: dict):
        """Отправляет лог публикации в группу"""
        try:
            log_text = f"""
✅ Пост опубликован

📍 Канал: {channel_config['name']}
📝 Тип: {post.get('type', 'неизвестно')}
📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}

🔗 ID поста: {post['id']}
            """

            await self.bot.send_message(
                chat_id=int(os.getenv("LEADS_GROUP_CHAT_ID", "-1003370698977")),
                text=log_text.strip(),
                message_thread_id=int(os.getenv("THREAD_ID_LOGS", "88"))
            )

        except Exception as e:
            logger.error(f"Failed to send publication log: {e}")


async def run_auto_poster(bot):
    """Запускает автопостинг"""
    poster = AutoPoster(bot)
    logger.info("🚀 AutoPoster запущен. Проверка каждые 10 минут.")

    while True:
        try:
            await poster.check_and_publish()
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в run_auto_poster: {e}")

        await asyncio.sleep(poster.check_interval)
