import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from handlers import start as common, quiz, dialog, invest, expert, price

logging.basicConfig(level=logging.INFO)

async def main():
    bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(common.router)
    dp.include_router(quiz.router)
    dp.include_router(expert.router)
    dp.include_router(price.router)
    dp.include_router(invest.router)
    dp.include_router(dialog.router)
    dp.include_router(quiz.router)
    dp.include_router(dialog.router)
    dp.include_router(invest.router)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())