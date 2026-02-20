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
from database.db import db
from services.publisher import publisher
import aiohttp
from config import LEADS_GROUP_CHAT_ID, THREAD_ID_LOGS, TERION_CHANNEL_ID, DOM_GRAND_CHANNEL_ID

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
        """Получает конфигурацию канала"""
        configs = {
            'terion': {
                'name': 'ТЕРИОН',
                'chat_id': TERION_CHANNEL_ID
            },
            'dom_grand': {
                'name': 'ДОМ ГРАНД',
                'chat_id': DOM_GRAND_CHANNEL_ID
            }
        }
        return configs.get(channel_key, configs['terion'])

    async def _publish_to_channel(self, post: dict, channel_config: dict) -> bool:
        """Публикует пост в конкретный канал TG + кросс-постинг в VK/Max через Publisher"""
        try:
            text = self._format_post_text(post)
            title = post.get('title', '')
            image_url = post.get('image_url')
            image_bytes = None

            # Если есть URL изображения, скачиваем его
            if image_url and image_url.startswith('http'):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_url, timeout=30) as resp:
                            if resp.status == 200:
                                image_bytes = await resp.read()
                                logger.info(f"✅ Изображение скачано ({len(image_bytes)} байт)")
                except Exception as e:
                    logger.error(f"⚠️ Не удалось скачать изображение по ссылке {image_url}: {e}")

            results = {}
            # 1. Публикация в конкретный TG канал
            results['tg'] = await publisher.publish_to_telegram(channel_config['chat_id'], text, image_bytes)

            # 2. Кросс-постинг в VK
            results['vk'] = await publisher.publish_to_vk(text, image_bytes)

            # 3. Кросс-постинг в Max.ru
            results['max'] = await publisher.publish_to_max(text, title)

            return results.get('tg', False)

        except Exception as e:
            logger.error(f"❌ Ошибка публикации: {e}")
            return False

    async def _publish_to_vk(self, post: dict) -> bool:
        """Публикует пост в VK"""
        try:
            if not vk_service.vk_token:
                logger.warning("VK не настроен, пропуск")
                return False

            # Форматируем текст для VK (без HTML)
            title = post.get('title', '') or ''
            body = post.get('body', '') or ''
            cta = post.get('cta', '') or ''

            vk_text = f"{title}\n\n{body}\n\n{cta}" if title else f"{body}\n\n{cta}"

            # Публикуем
            if post.get('image_url'):
                # Если image_url это локальный путь - скачиваем и публикуем
                image_path = post['image_url']
                if image_path.startswith('http'):
                    # Это URL - просто публикуем ссылку
                    await vk_service.post(vk_text)
                else:
                    # Локальный файл
                    await vk_service.post_with_photos(vk_text, [image_path])
            else:
                await vk_service.post(vk_text)

            logger.info("✅ Пост опубликован в VK")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка публикации в VK: {e}")
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
                chat_id=LEADS_GROUP_CHAT_ID,
                text=log_text.strip(),
                message_thread_id=THREAD_ID_LOGS
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
