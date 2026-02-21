"""
Скрипт для автономного запуска LeadHunter.
"""
import asyncio
import logging
import sys
import os

# Добавляем текущую директорию в путь импорта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.lead_hunter import LeadHunter
from database.db import db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("LeadHunterRunner")

async def main():
    logger.info("🎯 Запуск автономного охотника за лидами...")
    await db.connect()
    hunter = LeadHunter()

    while True:
        try:
            await hunter.hunt()
        except Exception as e:
            logger.error(f"❌ Ошибка в цикле охоты: {e}")

        # Пауза 30 минут
        logger.info("😴 Сон 30 минут до следующей охоты...")
        await asyncio.sleep(1800)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Остановка охотника...")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
