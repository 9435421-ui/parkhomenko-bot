from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from database.db import db

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    # Проверка роли пользователя
    user = await db.get_user(message.from_user.id)
    if not user:
        # В MVP можно добавить первого пользователя как админа или просто уведомлять
        await message.answer("Добро пожаловать в Контент-центр ТЕРИОН. У вас пока нет доступа к управлению.")
        return

    role = user['role']
    await message.answer(
        f"Здравствуйте, {message.from_user.first_name}! Ваша роль: {role}.\n"
        "Используйте меню для управления контент-планом и публикациями."
    )

# Добавим метод получения пользователя в БД (нужно обновить db.py)
