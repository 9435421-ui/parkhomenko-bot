"""
Middleware для модерации (бан и анти-мат)
"""
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message
from database.db import db
from utils.moderation import contains_bad_words

class ModerationMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        # Проверяем только сообщения
        if not isinstance(event, Message):
            return await handler(event, data)

        user_id = event.from_user.id

        # 1. Проверка на бан
        if await db.is_user_banned(user_id):
            await event.answer("Доступ ограничен за нарушение правил общения.")
            return

        # 2. Проверка на мат в текстовых сообщениях
        if event.text and contains_bad_words(event.text):
            await db.ban_user(user_id)
            await event.answer("Доступ ограничен за нарушение правил общения.")
            return

        return await handler(event, data)
