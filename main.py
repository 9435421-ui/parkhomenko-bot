import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from database import db
from handlers import start_router, quiz_router, dialog_router, invest_router, content_router, spy_router

logging.basicConfig(level=logging.INFO)

async def main():
    # Подключение к БД
    await db.connect()

    # Инициализация бота
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация роутеров
    dp.include_router(start_router)
    dp.include_router(quiz_router)
    dp.include_router(invest_router)
    dp.include_router(dialog_router)
    dp.include_router(content_router)
    dp.include_router(spy_router)

    print("🚀 Бот ТЕРИОН (Фаза 2) запущен!")
    try:
        await dp.start_polling(bot)
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
