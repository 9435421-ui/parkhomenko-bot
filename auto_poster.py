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
        """Проверка и публикация готового контента (только один самый старый пост за цикл)"""
        try:
            posts = await db.get_posts_to_publish()
            if not posts:
                logger.info("📭 Нет постов для публикации")
                return

            # Берем только самый старый пост (первый в списке, если они отсортированы по дате)
            post = posts[0]
            logger.info(f"📋 Найдено {len(posts)} постов. Обрабатываем самый старый: #{post.get('id')}")

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
                else:
                    logger.warning(f"⚠️ Пост #{post.get('id')} не опубликован (проверьте логи выше)")

            except Exception as e:
                logger.error(f"❌ Ошибка публикации поста #{post.get('id')}: {e}")

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
            text = self._format_post_text(post, platform="telegram")
            title = post.get("title", "") or ""
            image_url = post.get("image_url")
            image_prompt = post.get("image_prompt")
            image_bytes: bytes | None = None

            # ── ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЯ: Если image_url пустой, но есть image_prompt ────
            if not image_url or not image_url.strip():
                if image_prompt:
                    try:
                        logger.info(f"🖼️ Генерация изображения для поста #{post.get('id')}...")
                        from handlers.content import _auto_generate_image
                        import base64
                        image_b64 = await _auto_generate_image(image_prompt)
                        if image_b64:
                            image_bytes = base64.b64decode(image_b64)
                            logger.info(f"✅ Изображение сгенерировано для поста #{post.get('id')}")
                        else:
                            logger.warning(f"⚠️ Не удалось сгенерировать изображение для поста #{post.get('id')}")
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка генерации изображения для поста #{post.get('id')}: {e}")
                
                if not image_bytes:
                    logger.warning(f"⏸️ Пост #{post.get('id')} пропущен: image_url пустой и генерация не удалась.")
                    return False

            # Скачиваем изображение по URL (если не было сгенерировано выше)
            if not image_bytes and image_url:
                if image_url.startswith("http"):
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                image_url, timeout=aiohttp.ClientTimeout(total=30)
                            ) as resp:
                                if resp.status == 200:
                                    image_bytes = await resp.read()
                                    if image_bytes and len(image_bytes) > 0:
                                        logger.info(
                                            f"✅ Изображение скачано ({len(image_bytes)} байт)"
                                        )
                                    else:
                                        logger.warning(f"⚠️ Пост #{post.get('id')} пропущен: изображение пустое")
                                        return False
                                else:
                                    logger.warning(f"⚠️ Пост #{post.get('id')} пропущен: HTTP {resp.status} при скачивании изображения")
                                    return False
                    except Exception as e:
                        logger.warning(f"⚠️ Пост #{post.get('id')} пропущен: ошибка скачивания изображения {image_url}: {e}")
                        return False
                elif image_url.startswith("file_id") or len(image_url) > 20:
                    # Telegram file_id - используем напрямую через bot.get_file
                    try:
                        from aiogram import Bot
                        from config import BOT_TOKEN
                        bot = Bot(token=BOT_TOKEN)
                        file = await bot.get_file(image_url)
                        image_bytes = await bot.download_file(file.file_path)
                        await bot.session.close()
                        logger.info(f"✅ Изображение загружено по file_id")
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка загрузки изображения по file_id: {e}")
                        return False
                else:
                    logger.warning(f"⚠️ Пост #{post.get('id')} пропущен: image_url не является валидным HTTP URL или file_id")
                    return False
            
            # Если всё ещё нет изображения, пропускаем пост
            if not image_bytes:
                logger.warning(f"⏸️ Пост #{post.get('id')} пропущен: нет изображения")
                return False

            # ── ПУБЛИКАЦИЯ ВО ВСЕ ПЛАТФОРМЫ: TG, VK, MAX ──────────────────────────────
            channel_id = channel_config['chat_id']
            results = {}
            
            # 1. Telegram (основной канал)
            text_tg = self._format_post_text(post, platform="telegram")
            results['telegram'] = await publisher.publish_to_telegram(channel_id, text_tg, image_bytes)
            
            # 2. VK (кросс-постинг)
            try:
                text_vk = self._format_post_text(post, platform="vk")
                # VK подпись уже добавляется в publish_to_vk, но убеждаемся что она есть
                results['vk'] = await publisher.publish_to_vk(text_vk, image_bytes, add_signature=True)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка публикации в VK: {e}")
                results['vk'] = False
            
            # 3. MAX.ru (кросс-постинг)
            try:
                text_max = self._format_post_text(post, platform="max")
                title = post.get("title", "") or ""
                results['max'] = await publisher.publish_to_max(text_max, title)
            except Exception as e:
                logger.warning(f"⚠️ Ошибка публикации в MAX: {e}")
                results['max'] = False
            
            # Успех если хотя бы одна платформа опубликовала
            success = any(results.values())
            
            if success:
                platforms_str = ", ".join([k for k, v in results.items() if v])
                logger.info(f"✅ Пост #{post.get('id')} опубликован в: {platforms_str}")
            else:
                logger.warning(f"⚠️ Пост #{post.get('id')} не опубликован ни в одной платформе")
            
            return success

        except Exception as e:
            logger.error(f"❌ Ошибка публикации: {e}")
            return False

    def _format_post_text(self, post: dict, platform: str = "telegram") -> str:
        """Форматирует текст поста с обязательным футером, хэштегами и подписью эксперта.
        
        Args:
            post: Данные поста из БД
            platform: Платформа публикации ("telegram", "vk", "max")
        
        Returns:
            str: Отформатированный текст поста
        """
        title = post.get('title', '') or ''
        body = post.get('body', '') or ''
        cta = post.get('cta', '') or ''
        
        # Определяем канал для выбора хэштегов
        channel_key = self._determine_channel(post)
        
        # Получаем ссылку на квиз из переменной окружения
        quiz_link = os.getenv("VK_QUIZ_LINK", "https://t.me/Parkhovenko_i_kompaniya_bot?start=quiz")
        
        # Базовые хэштеги для TERION
        base_hashtags = "#перепланировка #МЖИ #БТИ #TERION #согласование #Москва #МО"
        
        # Хэштеги для ДОМ ГРАНД
        if channel_key == 'dom_grand':
            hashtags = "#загородныйдом #строительство #коттедж #технадзор #ДОМГРАНД #Москва #МО"
        else:
            hashtags = base_hashtags

        parts = []
        if title:
            # Для Telegram используем HTML, для VK/MAX — обычный текст
            if platform == "telegram":
                parts.append(f"<b>{title}</b>")
            else:
                parts.append(title)
        if body:
            parts.append(body)
        if cta:
            parts.append(cta)
        
        # Объединяем текст для проверки
        text_so_far = "\n\n".join(parts)
        
        # ── ПОДПИСЬ ЭКСПЕРТА: Обязательна для всех платформ ────────────────────────
        expert_signature = "\n\n---\n🏡 Эксперт: Юлия Пархоменко\nКомпания: TERION"
        if "Эксперт: Юлия Пархоменко" not in text_so_far and "Юлия Пархоменко" not in text_so_far:
            parts.append(expert_signature)
            logger.info(f"✅ Добавлена подпись эксперта в пост #{post.get('id')}")
        
        # Обновляем text_so_far после добавления подписи
        text_so_far = "\n\n".join(parts)
        
        # Проверяем наличие ссылки на квиз
        has_quiz_link = quiz_link in text_so_far or "квиз" in text_so_far.lower() or "quiz" in text_so_far.lower()
        
        # Проверяем наличие обязательных хэштегов (#TERION и #перепланировка)
        has_required_hashtags = "#TERION" in text_so_far and "#перепланировка" in text_so_far
        
        # ОБЯЗАТЕЛЬНАЯ ПРОВЕРКА: Если отсутствуют хэштеги или ссылка на квиз, добавляем их принудительно
        if not has_quiz_link:
            footer = f"\n\n🧐 Узнайте стоимость вашей перепланировки за 1 минуту:\n👉 {quiz_link}"
            parts.append(footer)
            logger.info(f"✅ Добавлена ссылка на квиз в пост #{post.get('id')}")
        
        if not has_required_hashtags:
            # Добавляем обязательные хэштеги, если их нет
            parts.append(hashtags)
            logger.info(f"✅ Добавлены обязательные хэштеги (#TERION #перепланировка) в пост #{post.get('id')}")
        elif hashtags not in text_so_far:
            # Если хэштеги есть, но не те, что нужны - добавляем правильные
            parts.append(hashtags)
            logger.info(f"✅ Добавлены правильные хэштеги в пост #{post.get('id')}")

        final_text = "\n\n".join(parts)
        
        # Для VK и MAX убираем HTML теги
        if platform in ("vk", "max"):
            import re
            final_text = re.sub(r'<[^>]+>', '', final_text)
            final_text = re.sub(r'&nbsp;', ' ', final_text)
        
        return final_text

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
