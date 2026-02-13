#!/usr/bin/env python3
"""
Wrapper script to run both main bot and chat parser.
Run as: python run_all.py
"""
import asyncio
import logging
import sys

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Импорт модулей
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN


async def run_main_bot():
    """Запуск основного бота aiogram."""
    from main import router as main_router
    from handlers.content import content_router
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    dp.include_router(main_router)
    dp.include_router(content_router)
    
    logger.info("🚀 Запуск основного бота TERION...")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка в main bot: {e}")
    finally:
        await bot.session.close()


async def run_chat_parser():
    """Запуск парсера чатов."""
    logger.info("🚀 Запуск парсера чатов...")
    
    try:
        # Импорт внутри функции, чтобы избежать циклических импортов
        from chat_parser import start_monitoring
        await start_monitoring()
    except Exception as e:
        logger.error(f"❌ Ошибка в chat parser: {e}")


async def main():
    """Запуск обоих процессов."""
    logger.info("=" * 50)
    logger.info("🎯 TERION Bot + Chat Parser")
    logger.info("=" * 50)
    
    # Запускаем оба процесса параллельно
    await asyncio.gather(
        run_main_bot(),
        run_chat_parser()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Остановка...")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
