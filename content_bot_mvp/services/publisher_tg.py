import logging
from datetime import datetime
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from content_bot_mvp.database.db import db

class TelegramPublisher:
    def __init__(self, default_bot: Bot):
        self.default_bot = default_bot

    async def publish_item(self, item_id: int, bot_name: str = None) -> bool:
        """Публикует конкретный айтем из БД во все активные каналы выбранного бота"""
        try:
            if not bot_name:
                logging.error("bot_name is required for publication")
                return False

            # Получаем все активные конфиги каналов для этого бота
            bot_configs = await db.get_bot_configs(bot_name)
            if not bot_configs:
                logging.error(f"No active bot configs for {bot_name} found")
                return False

            # Получаем данные айтема
            async with db.conn.execute(
                "SELECT title, body, image_url, hashtags, quiz_link, target_channel_alias FROM content_items WHERE id = ?",
                (item_id,)
            ) as cursor:
                item = await cursor.fetchone()
                if not item:
                    logging.error(f"Item {item_id} not found")
                    return False

            # Проверяем наличие целевого канала (из айтема или из плана)
            target_alias = item['target_channel_alias']

            async with db.conn.execute(
                "SELECT target_channel_alias FROM content_plan WHERE content_item_id = ?",
                (item_id,)
            ) as cursor:
                plan_row = await cursor.fetchone()
                if plan_row and plan_row['target_channel_alias']:
                    target_alias = plan_row['target_channel_alias']

            overall_success = False

            for config in bot_configs:
                channel_alias = config['channel_alias']

                # Если указан конкретный целевой канал, пропускаем остальные
                if target_alias and target_alias != channel_alias:
                    logging.info(f"Skipping channel {channel_alias} as it doesn't match target {target_alias}")
                    continue

                token = config['bot_token']
                channel_id = config['tg_channel_id']

                try:
                    # Создаем временный инстанс бота для отправки
                    async with Bot(token=token) as current_bot:
                        # Формируем текст (Тело + Хэштеги)
                        text = f"<b>{item['title']}</b>\n\n{item['body']}"
                        if item['hashtags']:
                            text += f"\n\n{item['hashtags']}"

                        # Формируем клавиатуру (ссылка на квиз с трекингом)
                        url = item['quiz_link'] if item['quiz_link'] else "https://t.me/torion_bot"

                        keyboard = InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="Задать вопрос эксперту 💬", url=url)]
                        ])

                        # Отправка
                        if item['image_url'] and item['image_url'].startswith('http'):
                            msg = await current_bot.send_photo(
                                chat_id=channel_id,
                                photo=item['image_url'],
                                caption=text,
                                reply_markup=keyboard,
                                parse_mode="HTML"
                            )
                        else:
                            msg = await current_bot.send_message(
                                chat_id=channel_id,
                                text=text,
                                reply_markup=keyboard,
                                parse_mode="HTML"
                            )

                        # Сохраняем результат в план/лог
                        async with db.conn.cursor() as cursor:
                            # Обновляем статус айтема (считаем опубликованным если хотя бы в один канал ушло)
                            await cursor.execute(
                                "UPDATE content_items SET status = 'published', updated_at = ? WHERE id = ?",
                                (datetime.now(), item_id)
                            )
                            # Добавляем запись в content_plan (фиксируем факт публикации в конкретный канал)
                            await cursor.execute(
                                """INSERT INTO content_plan (content_item_id, published_at, published, channel_id)
                                   VALUES (?, ?, 1, ?)""",
                                (item_id, datetime.now(), channel_id)
                            )
                            await db.conn.commit()

                        await db.log_action(0, "published_to_tg", f"Bot: {bot_name}, Channel: {channel_id} ({channel_alias}), Item ID: {item_id}, Msg ID: {msg.message_id}", bot_name=bot_name, channel_id=channel_id, status="success")
                        overall_success = True
                        logging.info(f"Successfully published item {item_id} to channel {channel_alias} ({channel_id})")

                except Exception as e:
                    logging.error(f"Ошибка публикации Item {item_id} в канал {channel_alias} ({channel_id}): {e}")
                    await db.log_action(0, "publish_error", f"Bot: {bot_name}, Channel: {channel_id}, Item ID: {item_id}, Error: {str(e)}", bot_name=bot_name, status="error")

            return overall_success

        except Exception as e:
            logging.error(f"Глобальная ошибка публикации Item {item_id}: {e}")
            return False
