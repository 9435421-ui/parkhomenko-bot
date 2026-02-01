import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from handlers import start, quiz, dialog, invest
from database.db import db

logging.basicConfig(level=logging.INFO)

async def main():
    # Подключение к базе данных
    await db.connect()

    bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(quiz.router)
    dp.include_router(invest.router)
    dp.include_router(dialog.router)

    print("✅ Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())