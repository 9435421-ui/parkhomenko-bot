import logging
from datetime import datetime
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.db import db

class TelegramPublisher:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def publish_item(self, item_id: int, channel_id: int) -> bool:
        """Публикует конкретный айтем из БД в указанный канал"""
        try:
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

            # Формируем клавиатуру (в MVP базово, можно расширить по cta_type)
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Задать вопрос эксперту 💬", url="https://t.me/TerionProjectBot?start=content_bot")]
            ])

            # Отправка
            if item['image_url']:
                msg = await self.bot.send_photo(
                    chat_id=channel_id,
                    photo=item['image_url'],
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                msg = await self.bot.send_message(
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
                # Добавляем запись в content_plan или обновляем существующую
                await cursor.execute(
                    """INSERT INTO content_plan (content_item_id, publish_datetime, platform, published)
                       VALUES (?, ?, 'telegram', 1)""",
                    (item_id, datetime.now())
                )
                await db.conn.commit()

            await db.log_action(0, "published_to_tg", f"Item ID: {item_id}, Msg ID: {msg.message_id}")
            return True

        except Exception as e:
            logging.error(f"Ошибка публикации Item {item_id}: {e}")
            await db.log_action(0, "publish_error", f"Item ID: {item_id}, Error: {str(e)}")
            return False
