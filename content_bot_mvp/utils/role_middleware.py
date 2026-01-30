from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from database.db import db

class RoleMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)

        user_id = event.from_user.id
        user = await db.get_user(user_id)

        # В MVP если пользователя нет в базе - роль VIEWER
        if not user:
            role = 'VIEWER'
        else:
            role = user['role']

        data['role'] = role
        return await handler(event, data)
