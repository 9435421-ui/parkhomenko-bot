#!/usr/bin/env python3
"""
Скрипт для авторизации Telegram клиента на сервере
Используется для создания .session файла для Telethon
"""
import os
import sys
import logging
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

def main():
    """Основная функция авторизации"""
    logger.info("🚀 Запуск скрипта авторизации Telegram клиента...")
    
    # Загружаем переменные окружения
    if not load_env():
        logger.error("Не удалось загрузить переменные окружения")
        sys.exit(1)
    
    # Проверяем наличие API_ID и API_HASH
    api_id_str = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    
    if not api_id_str or not api_hash:
        logger.error("❌ Отсутствуют API_ID или API_HASH в переменных окружения")
        print("\n" + "="*50)
        print("ИНСТРУКЦИЯ ПО НАСТРОЙКЕ")
        print("="*50)
        print("1. Добавьте в .env файл:")
        print("   API_ID=ваш_api_id_от_Telegram")
        print("   API_HASH=ваш_api_hash_от_Telegram")
        print("2. Перезапустите скрипт")
        print("="*50 + "\n")
        sys.exit(1)
    
    try:
        API_ID = int(api_id_str)
    except ValueError:
        logger.error("❌ API_ID должен быть числом")
        sys.exit(1)
    
    # Импортируем Telethon
    try:
        from telethon.sync import TelegramClient
        from telethon.sessions import StringSession
    except ImportError:
        logger.error("❌ telethon не установлен")
        print("Установите: pip install telethon")
        sys.exit(1)
    
    # Создаем клиент
    client = TelegramClient('bot', API_ID, api_hash)
    
    try:
        # Запускаем клиент
        with client:
            logger.info("✅ Авторизация прошла успешно!")
            logger.info("✅ Файл bot.session создан")
            
            # Получаем строку сессии для резервной копии
            session_string = StringSession.save(client.session)
            logger.info(f"Строка сессии: {session_string[:50]}...")
            
    except Exception as e:
        logger.error(f"❌ Ошибка авторизации: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()