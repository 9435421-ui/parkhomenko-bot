from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional

class TelegramPublisher:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def publish_post(
        self,
        channel_id: int,
        text: str,
        image_url: Optional[str] = None,
        source_tag: str = "content_bot"
    ):
        """Публикует пост в Телеграм-канал с CTA-кнопками"""

        # Создаем кнопки с метками источника
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Задать вопрос эксперту 💬",
                    url=f"https://t.me/TerionProjectBot?start={source_tag}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Рассчитать стоимость 🧮",
                    url=f"https://t.me/TerionProjectBot?start=price_{source_tag}"
                )
            ]
        ])

        if image_url:
            return await self.bot.send_photo(
                chat_id=channel_id,
                photo=image_url,
                caption=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        else:
            return await self.bot.send_message(
                chat_id=channel_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

# Инициализация будет в main.py
