import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN
from handlers import start as common, quiz, dialog, invest
from database import db
from utils import kb, router_ai
from auto_poster import run_auto_poster

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def on_startup():
    """Инициализация при запуске"""
    # Подключаем БД
    await db.connect()
    
    # Индексируем базу знаний
    await kb.index_documents()
    
    print("✅ Бот готов к работе")
    print(f"📚 База знаний: {len(kb.documents)} документов")
    print(f"🧠 Router AI: {'подключен' if router_ai.api_key else 'не настроен'}")


async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(common.router)
    dp.include_router(quiz.router)
    dp.include_router(invest.router)
    dp.include_router(dialog.router)

    await on_startup()
    
    # Запускаем автопостинг в фоновом режиме
    asyncio.create_task(run_auto_poster(bot))
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
