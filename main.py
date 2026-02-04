import asyncio
import logging
from aiogram import Bot, Dispatcher, types
logging.basicConfig(level=logging.INFO)
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from database import init_db
from handlers import start as common, quiz, dialog, invest
# Ребрендинг на ТЕРИОН

# Импорт квиза
from handlers.quiz import start_quiz

logging.basicConfig(level=logging.INFO)

async def main():
    # Инициализация БД
    init_db()

    bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher(storage=MemoryStorage())

    # Обработчик команды /start с квизом
    @dp.message_handler(commands=["start"])
    async def start_handler(message: types.Message):
        if "quiz" in message.text.lower():
            await start_quiz(message)
        else:
            await common.start(message)

    dp.include_router(common.router)
    dp.include_router(quiz.router)
    dp.include_router(invest.router)
    dp.include_router(dialog.router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())