#!/usr/bin/env python3
"""
Автономный запуск LeadHunter с профессиональным расписанием.

Использование:
    python3 run_hunter.py

Особенности:
    - Использует AsyncioScheduler для планирования задач
    - Охота за лидами каждые 20 минут (без отчёта в чат, только в базу)
    - Итоговые отчёты строго в 9:00, 14:00 и 19:00 по Москве
    - Корректное открытие/закрытие соединения с БД (режим WAL) для избежания ошибки 'database is locked'
"""

import asyncio
import logging
import sys
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from pytz import timezone

# Добавляем путь
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.lead_hunter.hunter import LeadHunter
from database.db import db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("LeadHunterRunner")


async def scheduled_hunt():
    """Функция для периодической охоты за лидами.
    
    Важно: подключаемся к БД, делаем дело и закрываем соединение,
    чтобы избежать ошибки 'database is locked' при использовании WAL режима.
    """
    try:
        # Подключаемся к БД
        if db.conn is None:
            await db.connect()
        else:
            # Проверяем, что соединение живое
            try:
                async with db.conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
            except Exception:
                # Соединение разорвано, переподключаемся
                await db.connect()
        
        hunter = LeadHunter()
        logger.info("🏹 Запуск плановой охоты...")
        await hunter.hunt()
        logger.info("✅ Охота завершена успешно")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при охоте: {e}", exc_info=True)
    finally:
        # Закрываем соединение после каждой итерации
        try:
            if db.conn:
                await db.close()
                logger.debug("🔌 Соединение с БД закрыто")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при закрытии БД: {e}")


async def scheduled_report():
    """Функция для отправки итогового отчёта.
    
    Вызывается строго в 9:00, 14:00 и 19:00 по Москве.
    """
    try:
        # Подключаемся к БД
        if db.conn is None:
            await db.connect()
        else:
            try:
                async with db.conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
            except Exception:
                await db.connect()
        
        hunter = LeadHunter()
        logger.info("📊 Отправка итогового отчёта...")
        await hunter.send_daily_report()
        logger.info("✅ Отчёт отправлен")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке отчёта: {e}", exc_info=True)
    finally:
        # Закрываем соединение
        try:
            if db.conn:
                await db.close()
                logger.debug("🔌 Соединение с БД закрыто")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при закрытии БД: {e}")


async def main():
    """Главная функция для запуска LeadHunter с планировщиком."""
    logger.info("🚀 Запуск LeadHunter с профессиональным расписанием...")
    
    # Инициализируем планировщик с московским временем
    moscow_tz = timezone('Europe/Moscow')
    scheduler = AsyncIOScheduler(timezone=moscow_tz)
    
    # 1. Сама охота (поиск лидов) — каждые 20 минут (без отчёта в чат, только в базу)
    scheduler.add_job(
        scheduled_hunt,
        'interval',
        minutes=20,
        id='hunt_job',
        replace_existing=True
    )
    logger.info("✅ Задача охоты добавлена: каждые 20 минут")
    
    # 2. ИТОГОВЫЙ ОТЧЁТ — строго 3 раза в день (9:00, 14:00, 19:00 МСК)
    scheduler.add_job(
        scheduled_report,
        CronTrigger(hour="9,14,19", minute=0, timezone=moscow_tz),
        id='daily_report_job',
        replace_existing=True
    )
    logger.info("✅ Задача отчёта добавлена: 9:00, 14:00, 19:00 МСК")
    
    # Запускаем планировщик
    scheduler.start()
    logger.info("✅ Планировщик запущен")
    
    try:
        # Бесконечный цикл
        while True:
            await asyncio.sleep(1000)
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Охотник остановлен")
        scheduler.shutdown()
    finally:
        # Закрываем соединение с БД при выходе
        try:
            if db.conn:
                await db.close()
                logger.info("🔌 Соединение с БД закрыто")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при закрытии БД: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Остановка по запросу пользователя")
        sys.exit(0)
