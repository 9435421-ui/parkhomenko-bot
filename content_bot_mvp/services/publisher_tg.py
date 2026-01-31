import logging
from datetime import datetime
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from content_bot_mvp.database.db import db

class TelegramPublisher:
    def __init__(self, default_bot: Bot):
        self.default_bot = default_bot

    async def publish_item(self, item_id: int, bot_name: str = None) -> bool:
        """Публикует конкретный айтем из БД через выбранного бота"""
        try:
            # Если бот не указан, используем дефолтный и какой-то дефолтный канал?
            # Или лучше всегда требовать bot_name
            if not bot_name:
                logging.error("bot_name is required for publication")
                return False

            # Получаем конфиг бота
            bot_config = await db.get_bot_config(bot_name)
            if not bot_config:
                logging.error(f"Bot config for {bot_name} not found")
                return False

            token = bot_config['bot_token']
            channel_id = bot_config['tg_channel_id']

            # Создаем временный инстанс бота для отправки
            async with Bot(token=token) as current_bot:
                # Получаем данные айтема
                async with db.conn.execute(
                    "SELECT title, body, image_url, cta_type, cta_link FROM content_items WHERE id = ?",
                    (item_id,)
                ) as cursor:
                    item = await cursor.fetchone()
                    if not item:
                        return False

                # Формируем текст
                text = f"<b>{item['title']}</b>\n\n{item['body']}"

                # Формируем клавиатуру (в MVP базово, всегда ведем на основной бот ТОРИОН)
                # Если айтем из архивного бота, ссылка все равно ведет на TorionProjectBot
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="Задать вопрос эксперту 💬", url="https://t.me/TorionProjectBot?start=content_bot")]
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
                    # Обновляем статус айтема
                    await cursor.execute(
                        "UPDATE content_items SET status = 'published', updated_at = ? WHERE id = ?",
                        (datetime.now(), item_id)
                    )
                    # Добавляем запись в content_plan
                    await cursor.execute(
                        """INSERT INTO content_plan (content_item_id, published_at, published)
                           VALUES (?, ?, 1)""",
                        (item_id, datetime.now())
                    )
                    await db.conn.commit()

                await db.update_bot_status(bot_name, "success")
                await db.log_action(0, "published_to_tg", f"Bot: {bot_name}, Channel: {channel_id}, Item ID: {item_id}, Msg ID: {msg.message_id}", bot_name=bot_name, channel_id=channel_id, status="success")
                return True

        except Exception as e:
            logging.error(f"Ошибка публикации Item {item_id} через {bot_name}: {e}")
            if bot_name:
                await db.update_bot_status(bot_name, f"error: {str(e)}")
            await db.log_action(0, "publish_error", f"Bot: {bot_name}, Item ID: {item_id}, Error: {str(e)}", bot_name=bot_name, status="error")
            return False
