import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

load_dotenv()

async def main():
    logging.basicConfig(level=logging.INFO)

    bot_token = os.getenv("CONTENT_BOT_TOKEN")
    if not bot_token:
        print("❌ CONTENT_BOT_TOKEN not found in .env")
        return

    bot = Bot(token=bot_token)
    dp = Dispatcher()

    # Инициализация БД
    from database.db import db
    await db.connect()

    # Middleware
    from utils.role_middleware import RoleMiddleware
    dp.message.middleware(RoleMiddleware())
    dp.callback_query.middleware(RoleMiddleware())

    # Регистрация роутеров
    from handlers import start, planner
    from handlers.admin import review
    dp.include_router(start.router)
    dp.include_router(planner.router)
    dp.include_router(review.router)

    # Запуск планировщика
    from services.scheduler import start_scheduler
    asyncio.create_task(start_scheduler(bot))

    print("🚀 Контент-бот ТОРИОН запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Бот остановлен")
