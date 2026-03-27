#!/usr/bin/env python3
"""
Wrapper script to run both main bot and chat parser.
Run as: python run_all.py

ВНИМАНИЕ: Не запускайте run_all.py одновременно с main.py — один и тот же BOT_TOKEN
будет использоваться в двух процессах → TelegramConflictError (409).
Для продакшена используйте только main.py.
"""
import asyncio
import logging
import sys
from pathlib import Path

# Не запускать, если уже работает main.py (bot.lock)
_lock = Path(__file__).resolve().parent / "bot.lock"
if _lock.exists():
    print("ERROR: main.py уже запущен (найден bot.lock). Не запускайте run_all.py одновременно.")
    sys.exit(1)

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
    
    logger.info("🚀 Запуск основного бота GEORIS...")
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Ошибка в main bot: {e}")
    finally:
        await bot.session.close()


async def run_chat_parser():
    """Запуск парсера чатов через LeadHunter."""
    logger.info("🚀 Запуск парсера TG чатов через LeadHunter...")
    
    try:
        # Используем новую структуру из services/lead_hunter/
        from services.lead_hunter.hunter import LeadHunter
        from database import db
        
        # Подключаем БД
        await db.connect()
        
        # Создаем экземпляр LeadHunter
        hunter = LeadHunter()
        
        # Запускаем поиск лидов (будет выполняться по расписанию через APScheduler)
        # Для run_all.py запускаем один раз, затем периодически
        logger.info("🔍 Запуск поиска лидов...")
        await hunter.hunt()
        
        # Периодический запуск каждые 30 минут
        import asyncio
        while True:
            await asyncio.sleep(1800)  # 30 минут
            await hunter.hunt()
    except Exception as e:
        logger.error(f"❌ Ошибка в LeadHunter: {e}", exc_info=True)


async def run_vk_parser():
    """Запуск мониторинга VK групп."""
    logger.info("🚀 Запуск мониторинга VK...")
    
    try:
        from vk_parser import start_vk_monitoring
        from database import db
        
        # Подключаем БД
        await db.connect()
        
        # Получаем VK группы из БД
        vk_resources = await db.get_target_resources(resource_type="vk")
        
        if vk_resources:
            groups = [r['link'].replace('vk.com/', '') for r in vk_resources]
            logger.info(f"📘 Мониторинг VK групп: {groups}")
            await start_vk_monitoring(groups, interval=300)
        else:
            logger.info("📘 Нет VK групп для мониторинга")
            # Делаем бесконечный цикл ожидания
            while True:
                await asyncio.sleep(60)
    except Exception as e:
        logger.error(f"❌ Ошибка в VK parser: {e}")


async def main():
    """Запуск обоих процессов."""
    logger.info("=" * 50)
    logger.info("🎯 GEORIS Bot + Chat Parser")
    logger.info("=" * 50)
    
    # Запускаем все процессы параллельно
    await asyncio.gather(
        run_main_bot(),
        run_chat_parser(),
        run_vk_parser()
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Остановка...")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
