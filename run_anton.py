#!/usr/bin/env python3
"""
Запуск бота АНТОН с автоматическим восстановлением базы данных
"""
import os
import sys
import logging
import shutil
import sqlite3
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
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