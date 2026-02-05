import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from handlers import start_router, quiz_router, dialog_router, invest_router, content, spy

logging.basicConfig(level=logging.INFO)

async def main():
    # Инициализация бота
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация роутеров
    dp.include_router(start_router)
    dp.include_router(quiz_router)
    dp.include_router(invest_router)
    dp.include_router(dialog_router)
    dp.include_router(content.router)
    dp.include_router(spy.router)

    print("🚀 Бот ТЕРИОН (Фаза 2) запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
