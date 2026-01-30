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

@router.message(Command("add_bot_config"))
async def cmd_add_bot(message: Message, role: str):
    if role != 'ADMIN':
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split()
    if len(args) < 4:
        await message.answer("📝 Формат: /add_bot_config [name] [token] [channel_id] [description...]")
        return

    bot_name = args[1]
    token = args[2]
    try:
        channel_id = int(args[3])
    except ValueError:
        await message.answer("❌ Channel ID должен быть числом.")
        return

    description = " ".join(args[4:]) if len(args) > 4 else ""

    await db.add_bot_config(bot_name, token, channel_id, description)
    await message.answer(f"✅ Бот {bot_name} успешно сконфигурирован для канала {channel_id}!")
