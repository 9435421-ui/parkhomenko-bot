#!/usr/bin/env python3
"""
Скрипт авторизации Telethon сессии для модуля Discovery.
Создает файл сессии 'anton_parser.session', который используется для поиска новых чатов/групп.

Использование:
    python auth_session.py

Требования:
    - API_ID и API_HASH должны быть заданы в .env
    - Номер телефона вводится при запуске скрипта
"""
import os
import sys
import time
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError

# Загружаем переменные окружения из .env
load_dotenv()

# API credentials для авторизации Telethon сессии (читаем из .env)
api_id_str = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Проверяем наличие обязательных переменных
if not api_id_str or not API_HASH:
    print("=" * 60)
    print("❌ ОШИБКА: API_ID и API_HASH не заданы в .env")
    print("=" * 60)
    print("\n📝 Сначала заполни .env на сервере!")
    print("\nДобавьте в файл .env следующие строки:")
    print("API_ID=your_telegram_api_id")
    print("API_HASH=your_telegram_api_hash")
    print("\nПолучить API можно на https://my.telegram.org/apps")
    print("=" * 60)
    sys.exit(1)

# Преобразуем API_ID в int
try:
    API_ID = int(api_id_str)
except ValueError:
    print("=" * 60)
    print("❌ ОШИБКА: API_ID должен быть числом")
    print("=" * 60)
    print(f"Получено: {api_id_str}")
    print("Проверьте значение API_ID в файле .env")
    print("=" * 60)
    sys.exit(1)

# Имя файла сессии (должно совпадать с тем, что используется в Discovery)
SESSION_NAME = 'anton_parser'


async def main():
    """Основная функция авторизации"""
    # Проверяем версию Telethon
    try:
        import telethon
        telethon_version = telethon.__version__
    except:
        telethon_version = "неизвестна"
    
    print("=" * 60)
    print("🔐 АВТОРИЗАЦИЯ TELEGRAM СЕССИИ ДЛЯ DISCOVERY")
    print("=" * 60)
    print(f"\n📁 Файл сессии: {SESSION_NAME}.session")
    print(f"🔑 API ID: {API_ID}")
    print(f"🔑 API Hash: {API_HASH[:10]}...")

    print(f"�📦 Telethon версия: {telethon_version}")
    print("\n" + "-" * 60)
    
    # Создаем клиент Telethon
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    try:
        print("\n📱 Подключение к Telegram...")
        await client.connect()
        
        # Проверяем, авторизован ли уже
        if await client.is_user_authorized():
            print("✅ Сессия уже авторизована!")
            me = await client.get_me()
            print(f"👤 Авторизован как: {me.first_name} {me.last_name or ''} (@{me.username or 'без username'})")
            print(f"🆔 User ID: {me.id}")
            print("\n✅ Готово! Модуль Discovery может использовать эту сессию.")
            await client.disconnect()
            return
        
        # Если не авторизован, запрашиваем номер телефона
        print("\n📞 Введите номер телефона в международном формате:")
        print("   Пример: +79991234567")
        phone = input("Номер: ").strip()
        
        if not phone:
            print("❌ Номер телефона не может быть пустым")
            await client.disconnect()
            return
        
        # Отправляем код подтверждения
        print(f"\n📨 Отправка кода подтверждения на {phone}...")
        # Небольшая пауза перед отправкой кода
        await asyncio.sleep(2)
        try:
            await client.send_code_request(phone)
        except FloodWaitError as e:
            print(f"⏳ Flood wait: Telegram заблокировал на {e.seconds} секунд")
            await asyncio.sleep(e.seconds)
            await client.send_code_request(phone)
        
        # Запрашиваем код подтверждения
        print("\n🔐 Введите код подтверждения из Telegram:")
        print("💡 Если код не пришел в течение 30 секунд, попробуйте:")
        print("   - Перезапустить скрипт")
        print("   - Проверить раздел 'Устройства' в настройках Telegram")
        print("   - Убедиться, что номер телефона введен правильно")
        code = input("\nКод: ").strip()
        
        if not code:
            print("❌ Код подтверждения не может быть пустым")
            await client.disconnect()
            return
        
        try:
            # Пытаемся войти с кодом
            await client.sign_in(phone, code)
            
        except SessionPasswordNeededError:
            # Если требуется двухфакторная аутентификация
            print("\n🔒 Включена двухфакторная аутентификация (2FA)")
            print("Введите пароль:")
            password = input("Пароль: ").strip()
            
            if not password:
                print("❌ Пароль не может быть пустым")
                await client.disconnect()
                return
            
            await client.sign_in(password=password)
        
        # Проверяем успешность авторизации
        if await client.is_user_authorized():
            me = await client.get_me()
            print("\n" + "=" * 60)
            print("✅ АВТОРИЗАЦИЯ УСПЕШНА!")
            print("=" * 60)
            print(f"👤 Имя: {me.first_name} {me.last_name or ''}")
            print(f"📱 Username: @{me.username or 'не задан'}")
            print(f"🆔 User ID: {me.id}")
            print(f"📁 Сессия сохранена в: {SESSION_NAME}.session")
            print("\n✅ Теперь модуль Discovery может использовать эту сессию для поиска чатов!")
            print("=" * 60)
        else:
            print("\n❌ Ошибка: авторизация не завершена")
        
    except Exception as e:
        print(f"\n❌ Ошибка авторизации: {e}")
        print("\nВозможные причины:")
        print("  - Неверный номер телефона")
        print("  - Неверный код подтверждения")
        print("  - Неверный пароль 2FA")
        print("  - Проблемы с подключением к Telegram")
    
    finally:
        await client.disconnect()
        print("\n🔌 Соединение закрыто")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️ Прервано пользователем")
        sys.exit(0)
