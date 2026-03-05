#!/usr/bin/env python3
"""
Скрипт для авторизации Telegram клиента на сервере
Используется для создания .session файла для Telethon
"""
import os
import sys
import logging
import asyncio
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
        logger.error("Текущее значение API_ID: " + repr(api_id_str))
        logger.error("Проверьте .env файл и убедитесь, что API_ID содержит только цифры")
        sys.exit(1)
    
    # Импортируем Telethon
    try:
        from telethon.sync import TelegramClient
        from telethon.sessions import StringSession
        from telethon.errors import (
            FloodWaitError,
            PhoneNumberInvalidError,
            PhoneCodeInvalidError,
            PhoneCodeExpiredError,
            SessionPasswordNeededError,
            AuthKeyUnregisteredError,
            AuthKeyInvalidError,
            UserDeactivatedBanError,
            UserDeactivatedError,
            PhoneNumberBannedError,
            PhonePasswordFloodError,
            PhonePasswordProtectedError,
            SessionRevokedError,
            SessionExpiredError,
            TimeoutError
        )
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
            
    except FloodWaitError as e:
        logger.error(f"❌ FloodWait ошибка: Telegram заблокировал запросы на {e.seconds} секунд")
        logger.error("Это защита от спама. Подождите указанное время и попробуйте снова")
        logger.error("Рекомендация: уменьшите частоту запросов или используйте другой аккаунт")
        sys.exit(1)
        
    except PhoneNumberInvalidError as e:
        logger.error("❌ Неверный формат номера телефона")
        logger.error("Проверьте, что номер указан в правильном формате (например, +79123456789)")
        sys.exit(1)
        
    except PhoneNumberBannedError as e:
        logger.error("❌ Номер телефона заблокирован в Telegram")
        logger.error("Этот номер не может использоваться для авторизации")
        logger.error("Рекомендация: используйте другой номер телефона")
        sys.exit(1)
        
    except PhoneCodeInvalidError as e:
        logger.error("❌ Неверный код подтверждения")
        logger.error("Код, который вы ввели, не соответствует отправленному")
        logger.error("Рекомендация: запросите новый код и введите его внимательно")
        sys.exit(1)
        
    except PhoneCodeExpiredError as e:
        logger.error("❌ Срок действия кода подтверждения истек")
        logger.error("Код больше не действителен, запросите новый")
        logger.error("Рекомендация: запросите новый код подтверждения")
        sys.exit(1)
        
    except SessionPasswordNeededError as e:
        logger.error("❌ Требуется двухфакторная аутентификация")
        logger.error("На аккаунте включена 2FA, необходимо ввести пароль")
        logger.error("Рекомендация: введите пароль от двухфакторной аутентификации")
        sys.exit(1)
        
    except AuthKeyUnregisteredError as e:
        logger.error("❌ Сессия не зарегистрирована")
        logger.error("Ключ авторизации не найден на серверах Telegram")
        logger.error("Рекомендация: удалите файл bot.session и начните авторизацию заново")
        sys.exit(1)
        
    except AuthKeyInvalidError as e:
        logger.error("❌ Недействительный ключ авторизации")
        logger.error("Ключ авторизации поврежден или не соответствует требованиям")
        logger.error("Рекомендация: удалите файл bot.session и начните авторизацию заново")
        sys.exit(1)
        
    except UserDeactivatedBanError as e:
        logger.error("❌ Аккаунт заблокирован администрацией Telegram")
        logger.error("Этот аккаунт не может использоваться для авторизации")
        logger.error("Рекомендация: используйте другой аккаунт")
        sys.exit(1)
        
    except UserDeactivatedError as e:
        logger.error("❌ Аккаунт удален пользователем")
        logger.error("Этот аккаунт был удален и не может использоваться")
        logger.error("Рекомендация: используйте другой аккаунт")
        sys.exit(1)
        
    except PhonePasswordFloodError as e:
        logger.error("❌ Слишком много попыток ввода пароля")
        logger.error("Вы превысили лимит попыток ввода пароля двухфакторной аутентификации")
        logger.error("Рекомендация: подождите некоторое время и попробуйте снова")
        sys.exit(1)
        
    except PhonePasswordProtectedError as e:
        logger.error("❌ Аккаунт защищен паролем")
        logger.error("На аккаунте включена защита, необходимо ввести пароль")
        logger.error("Рекомендация: введите пароль от аккаунта")
        sys.exit(1)
        
    except SessionRevokedError as e:
        logger.error("❌ Сессия была отозвана")
        logger.error("Сессия была отозвана владельцем аккаунта")
        logger.error("Рекомендация: удалите файл bot.session и начните авторизацию заново")
        sys.exit(1)
        
    except SessionExpiredError as e:
        logger.error("❌ Сессия истекла")
        logger.error("Срок действия сессии закончился")
        logger.error("Рекомендация: удалите файл bot.session и начните авторизацию заново")
        sys.exit(1)
        
    except TimeoutError as e:
        logger.error("❌ Таймаут соединения")
        logger.error("Не удалось установить соединение с серверами Telegram")
        logger.error("Рекомендация: проверьте интернет-соединение и попробуйте снова")
        sys.exit(1)
        
    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"❌ Неизвестная ошибка авторизации: {error_type}")
        logger.error(f"Сообщение об ошибке: {str(e)}")
        
        # Дополнительная диагностика
        if "code" in str(e).lower():
            logger.error("🔍 Похоже, проблема связана с кодом подтверждения")
            logger.error("Проверьте:")
            logger.error("  - Приходит ли SMS/Telegram код на ваш номер")
            logger.error("  - Не истек ли срок действия кода")
            logger.error("  - Правильно ли вы вводите код")
        elif "session" in str(e).lower() or "auth" in str(e).lower():
            logger.error("🔍 Похоже, проблема связана с сессией или авторизацией")
            logger.error("Проверьте:")
            logger.error("  - Существует ли файл bot.session")
            logger.error("  - Не поврежден ли файл сессии")
            logger.error("  - Не изменились ли API_ID или API_HASH")
        elif "phone" in str(e).lower():
            logger.error("🔍 Похоже, проблема связана с номером телефона")
            logger.error("Проверьте:")
            logger.error("  - Правильно ли указан номер")
            logger.error("  - Не заблокирован ли номер")
            logger.error("  - Активен ли аккаунт на этом номере")
        else:
            logger.error("🔍 Общие рекомендации:")
            logger.error("  - Проверьте интернет-соединение")
            logger.error("  - Убедитесь, что API_ID и API_HASH верны")
            logger.error("  - Попробуйте перезапустить скрипт")
            logger.error("  - Если проблема persists, удалите bot.session и начните заново")
        
        sys.exit(1)

if __name__ == "__main__":
    main()