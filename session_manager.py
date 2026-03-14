<<<<<<< HEAD
import os
import sys
import asyncio
import argparse
from telethon import TelegramClient
from config import API_ID, API_HASH

SESSION_NAME = "anton_parser"

async def check_session():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.connect()
    is_auth = await client.is_user_authorized()
    await client.disconnect()
    return is_auth

async def create_session(reset=False):
    session_file = f"{SESSION_NAME}.session"
    if reset and os.path.exists(session_file):
        os.remove(session_file)
        print(f"🗑️ Session file {session_file} removed.")

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    print("✅ Session created successfully!")
    me = await client.get_me()
    print(f"👤 Authorized as: {me.first_name} (@{me.username})")
    await client.disconnect()

def main():
    parser = argparse.ArgumentParser(description="Telegram Session Manager")
    parser.add_argument("--reset", action="store_true", help="Force recreate session")
    parser.add_argument("--check", action="store_true", help="Check if session is valid")
    args = parser.parse_args()

    if args.check:
        is_valid = asyncio.run(check_session())
        if is_valid:
            print("✅ Session is valid")
            sys.exit(0)
        else:
            print("❌ Session is invalid or not found")
            sys.exit(1)
    
    asyncio.run(create_session(reset=args.reset))

if __name__ == "__main__":
    main()
=======
"""
Session Manager — управление сессией Telethon для парсинга чатов.
При первом запуске запрашивает код подтверждения Telegram.
"""
import os
import sys
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv

load_dotenv()

# Настройки из .env
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")

# Путь к файлу сессии
SESSION_FILE = "anton_parser.session"


async def create_session():
    """
    Создает сессию Telethon. При первом запуске запрашивает код.
    """
    if not API_ID or not API_HASH or not PHONE:
        print("❌ Ошибка: не найдены API_ID, API_HASH или PHONE в .env")
        return None
    
    print(f"📱 Авторизация для номера: {PHONE}")
    print(f"   API_ID: {API_ID}")
    print(f"   API_HASH: {API_HASH[:10]}...")
    
    client = TelegramClient(SESSION_FILE, int(API_ID), API_HASH)
    
    try:
        await client.start(phone=PHONE)
        print("✅ Сессия создана успешно!")
        print(f"   Файл сессии: {SESSION_FILE}")
        return client
        
    except SessionPasswordNeededError:
        print("🔐 Требуется пароль двухфакторной аутентификации:")
        password = input("Введите пароль: ")
        await client.start(phone=PHONE, password=password)
        print("✅ Сессия создана с 2FA!")
        return client
        
    except Exception as e:
        print(f"❌ Ошибка при создании сессии: {e}")
        return None


async def get_client():
    """
    Возвращает существующий клиент или создает новый.
    """
    if os.path.exists(SESSION_FILE):
        print(f"📂 Найдена существующая сессия: {SESSION_FILE}")
        client = TelegramClient(SESSION_FILE, int(API_ID), API_HASH)
        
        # Проверяем, что сессия валидна
        try:
            await client.connect()
            if await client.is_user_authorized():
                print("✅ Сессия валидна!")
                return client
            else:
                print("⚠️ Сессия истекла, создаем новую...")
                await client.disconnect()
                return await create_session()
        except Exception as e:
            print(f"⚠️ Ошибка подключения: {e}")
            return await create_session()
    else:
        print("📄 Сессия не найдена, создаем новую...")
        return await create_session()


if __name__ == "__main__":
    import asyncio
    
    async def main():
        client = await get_client()
        if client:
            print("\n🎉 Готово! Сессия Telethon активна.")
            print("   Можно использовать client для парсинга чатов.")
            await client.disconnect()
        else:
            print("\n❌ Не удалось создать сессию.")
    
    asyncio.run(main())
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
