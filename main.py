"""
Основной бот ТЕРИОН - aiogram версия.
"""
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, GROUP_ID, THREAD_ID_LEADS
from handlers import start, quiz, dialog, admin
from database import db
from utils import kb, router_ai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальный экземпляр бота
bot: Bot = None
dp: Dispatcher = None


async def on_startup():
    """Инициализация при запуске"""
    global bot, dp
    
    # Подключаем БД
    await db.connect()
    
    # Индексируем базу знаний
    await kb.index_documents()
    
    print("✅ Бот ТЕРИОН готов!")
    print(f"📚 База знаний: {len(kb.documents)} документов")
    print(f"🧠 Router AI: {'подключен' if router_ai.api_key else 'не настроен'}")
    print(f"📤 Группа: {GROUP_ID} (thread: {THREAD_ID_LEADS})")


async def main():
    """Запуск бота"""
    global bot, dp
    
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML")
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем роутеры
    dp.include_router(start.router)
    dp.include_router(quiz.router)
    dp.include_router(dialog.router)
    dp.include_router(admin.router)

    await on_startup()
    
    print("🚀 Запуск поллинга...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
