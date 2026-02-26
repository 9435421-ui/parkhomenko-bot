#!/usr/bin/env python3
"""
Главный файл запуска системы TERION (Антон).

Функционал:
1. Инициализация базы данных
2. Запуск Scout Parser в бесконечном цикле (поиск лидов в TG и VK)
3. Режим модерации: все лиды отправляются в админ-канал для модерации
4. Использование фильтров анти-спама для защиты времени модератора

Использование:
    python run_anton.py
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.scout_parser import scout_parser
from services.lead_hunter.hunter import LeadHunter
from database.db import db

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("TERION")


async def init_database():
    """Инициализация базы данных"""
    try:
        logger.info("🔌 Инициализация базы данных...")
        if db.conn is None:
            await db.connect()
        logger.info("✅ База данных подключена")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}", exc_info=True)
        return False


async def run_scout_cycle():
    """Один цикл сканирования: парсинг TG и VK, поиск лидов, отправка на модерацию"""
    try:
        logger.info("🔍 Начало цикла сканирования...")
        
        # Проверяем соединение с БД
        if db.conn is None:
            await db.connect()
        
        # Обработка через LeadHunter
        # Метод hunt() автоматически:
        # 1. Вызывает scout_parser.parse_telegram() и parse_vk() с фильтрами анти-спама
        # 2. Анализирует найденные посты через AI (Yandex GPT → резервный ключ → Router AI)
        # 3. Сохраняет лиды в БД
        # 4. Отправляет карточки на модерацию в админ-канал (Режим Модерации)
        logger.info("🕵️ Запуск LeadHunter для поиска и обработки лидов...")
        hunter = LeadHunter()
        await hunter.hunt()
        
        logger.info("✅ Цикл сканирования завершен успешно")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в цикле сканирования: {e}", exc_info=True)
    finally:
        # Не закрываем соединение с БД, чтобы не было проблем с блокировкой
        pass


async def main():
    """Главная функция запуска системы TERION"""
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК СИСТЕМЫ TERION (Антон)")
    logger.info("=" * 60)
    logger.info(f"📅 Дата запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Проверка обязательных переменных окружения
    required_vars = [
        "BOT_TOKEN",
        "YANDEX_API_KEY",
        "FOLDER_ID",
        "LEADS_GROUP_CHAT_ID",
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"❌ Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
        logger.error("💡 Убедитесь, что файл .env настроен корректно")
        sys.exit(1)
    
    # Проверка резервного ключа (опционально)
    if os.getenv("YANDEX_API_KEY_BACKUP"):
        logger.info("✅ Резервный API-ключ Яндекса обнаружен")
    else:
        logger.info("ℹ️ Резервный API-ключ Яндекса не настроен (YANDEX_API_KEY_BACKUP)")
    
    # Инициализация базы данных
    if not await init_database():
        logger.error("❌ Не удалось инициализировать базу данных. Завершение работы.")
        sys.exit(1)
    
    logger.info("")
    logger.info("📋 Конфигурация системы:")
    logger.info(f"   • Режим модерации: ВКЛ (все лиды проходят через модерацию)")
    logger.info(f"   • Фильтры анти-спама: ВКЛ")
    logger.info(f"   • Fallback на Router AI: ВКЛ")
    logger.info(f"   • Резервный ключ Яндекса: {'ВКЛ' if os.getenv('YANDEX_API_KEY_BACKUP') else 'ВЫКЛ'}")
    logger.info("")
    
    # Интервал между циклами сканирования (в секундах)
    # По умолчанию: 20 минут (1200 секунд)
    scan_interval = int(os.getenv("SCOUT_SCAN_INTERVAL", "1200"))
    logger.info(f"⏰ Интервал сканирования: {scan_interval} секунд ({scan_interval // 60} минут)")
    logger.info("")
    logger.info("🔄 Запуск бесконечного цикла сканирования...")
    logger.info("   (Нажмите Ctrl+C для остановки)")
    logger.info("=" * 60)
    logger.info("")
    
    cycle_count = 0
    
    try:
        while True:
            cycle_count += 1
            logger.info(f"🔄 Цикл #{cycle_count} — {datetime.now().strftime('%H:%M:%S')}")
            
            await run_scout_cycle()
            
            logger.info(f"⏳ Ожидание {scan_interval} секунд до следующего цикла...")
            logger.info("")
            
            await asyncio.sleep(scan_interval)
            
    except KeyboardInterrupt:
        logger.info("")
        logger.info("=" * 60)
        logger.info("👋 Остановка системы TERION по запросу пользователя")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
    finally:
        # Закрываем соединение с БД при выходе
        try:
            if db.conn:
                await db.close()
                logger.info("🔌 Соединение с БД закрыто")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при закрытии БД: {e}")
        
        logger.info("✅ Система TERION остановлена")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Остановка по запросу пользователя")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Фатальная ошибка: {e}", exc_info=True)
        sys.exit(1)
