#!/usr/bin/env python3
"""
<<<<<<< HEAD
Запуск бота АНТОН с автоматическим восстановлением базы данных
"""
import os
import sys
import logging
import shutil
import sqlite3
from pathlib import Path
=======
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
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
<<<<<<< HEAD
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_env():
    """Загрузка переменных окружения из .env файла"""
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.getcwd(), '.env')
        logger.info(f"🔍 Текущая директория: {os.getcwd()}")
        logger.info(f"🔍 Проверка наличия .env: {os.path.exists(env_path)}")
        
        if os.path.exists(env_path):
            load_dotenv(env_path)
            logger.info(f"✅ Переменные окружения загружены из {env_path}")
        else:
            logger.warning(f"⚠️ Файл {env_path} не найден")
            
    except ImportError:
        logger.warning("Модуль python-dotenv не установлен")
        return False
    except Exception as e:
        logger.error(f"Ошибка загрузки .env файла: {e}")
        return False
    return True

def check_required_env_vars():
    """Проверка наличия всех необходимых переменных окружения"""
    required_vars = [
        'BOT_TOKEN', 'YANDEX_API_KEY', 'FOLDER_ID',
        'ADMIN_GROUP_ID', 'JULIA_USER_ID', 'ADMIN_ID'
    ]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
        print("\n" + "="*60)
        print("🚨 ОШИБКА: НЕ ХВАТАЕТ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ")
        print("="*60)
        print("Отсутствуют переменные:")
        for var in missing_vars:
            print(f"  • {var}")
        print("\nРешение:")
        print("1. Добавьте недостающие переменные в .env файл")
        print("2. Или установите их в системе")
        print("3. Перезапустите бота")
        print("="*60 + "\n")
        return False
    
    return True

def check_and_fix_database():
    """Проверка и восстановление базы данных"""
    db_path = Path("parkhomenko_bot.db")
    backup_path = Path("parkhomenko_bot.db.backup")
    
    if not db_path.exists():
        logger.info("База данных не найдена, создаем новую...")
        return True
    
    try:
        # Проверяем целостность базы данных
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA integrity_check")
        conn.close()
        logger.info("База данных цела")
        return True
    except sqlite3.DatabaseError as e:
        logger.error(f"База данных повреждена: {e}")
        
        # Пытаемся восстановить из бэкапа
        if backup_path.exists():
            logger.info("Восстанавливаем базу данных из бэкапа...")
            try:
                shutil.copy2(str(backup_path), str(db_path))
                logger.info("База данных восстановлена из бэкапа")
                return True
            except Exception as backup_error:
                logger.error(f"Ошибка восстановления из бэкапа: {backup_error}")
        
        # Создаем новую базу данных
        logger.info("Создаем новую базу данных...")
        try:
            if db_path.exists():
                db_path.unlink()
            # Импортируем и инициализируем базу данных
            from database.db import db
            import asyncio
            asyncio.run(db.connect())
            logger.info("Новая база данных создана")
            return True
        except Exception as init_error:
            logger.error(f"Ошибка создания новой базы данных: {init_error}")
            return False

def check_env_variables():
    """Проверка наличия необходимых переменных окружения"""
    required_vars = ['BOT_TOKEN', 'YANDEX_API_KEY', 'FOLDER_ID']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
        print("\n" + "="*50)
        print("ИНСТРУКЦИЯ ПО НАСТРОЙКЕ ОКРУЖЕНИЯ")
        print("="*50)
        print("1. Создайте файл .env в корне проекта")
        print("2. Добавьте следующие переменные:")
        print("   BOT_TOKEN=ваш_токен_бота")
        print("   YANDEX_API_KEY=ваш_ключ_YandexGPT")
        print("   FOLDER_ID=ваш_folder_id")
        print("3. Перезапустите бота")
        print("="*50 + "\n")
        return False
    
    return True

def main():
    """Основная функция запуска бота"""
    logger.info("🚀 Запуск бота АНТОН...")
    
    # Загружаем переменные окружения
    load_env()
    
    # Проверяем и восстанавливаем базу данных
    if not check_and_fix_database():
        logger.error("Не удалось восстановить базу данных")
        sys.exit(1)
    
    # Проверяем переменные окружения
    if not check_required_env_vars():
        logger.error("Проверьте настройку окружения")
        sys.exit(1)
    
    # Создаем бэкап базы данных
    db_path = Path("parkhomenko_bot.db")
    backup_path = Path("parkhomenko_bot.db.backup")
    if db_path.exists():
        try:
            shutil.copy2(str(db_path), str(backup_path))
            logger.info("Создан бэкап базы данных")
        except Exception as e:
            logger.warning(f"Не удалось создать бэкап: {e}")
    
    # Запускаем основной бот
    try:
        from bot_anton import start_anton_bot
        import asyncio
        asyncio.run(start_anton_bot())
    except KeyboardInterrupt:
        logger.info("🛑 Бот АНТОН остановлен")
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
=======
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
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
