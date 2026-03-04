"""
Session Manager — управление сессией Telethon для парсинга чатов.
При первом запуске запрашивает код подтверждения Telegram.
"""
import os
import sys
import re
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneNumberInvalidError
from dotenv import load_dotenv

load_dotenv()

# Настройки из .env (через config или напрямую)
try:
    from config import API_ID, API_HASH, PHONE
except ImportError:
    API_ID = os.getenv("API_ID")
    API_HASH = os.getenv("API_HASH")
    PHONE = os.getenv("PHONE")

# Путь к файлу сессии
SESSION_FILE = "anton_parser.session"


def validate_phone(phone: str) -> str:
    """Проверяет и нормализует формат телефона."""
    if not phone:
        return ""
    # Оставляем только цифры
    clean_phone = re.sub(r'\D', '', phone)
    if not clean_phone.startswith('+'):
        clean_phone = '+' + clean_phone
    return clean_phone


async def create_session():
    """
    Создает сессию Telethon. При первом запуске запрашивает код.
    """
    global PHONE
    if not API_ID or not API_HASH or not PHONE:
        print("❌ Ошибка: не найдены API_ID, API_HASH или PHONE в .env")
        print("   Проверьте наличие этих переменных в файле .env")
        return None
    
    PHONE = validate_phone(PHONE)

    print(f"📱 Подготовка авторизации для: {PHONE}")
    print(f"   API_ID: {API_ID}")
    
    # Если файл сессии есть, но мы здесь — значит он невалидный. Удаляем его для чистого входа.
    if os.path.exists(SESSION_FILE):
        print(f"🧹 Удаление старого нерабочего файла сессии {SESSION_FILE}...")
        try:
            os.remove(SESSION_FILE)
        except Exception as e:
            print(f"⚠️ Не удалось удалить файл: {e}")

    client = TelegramClient(SESSION_FILE, int(API_ID), API_HASH)
    
    try:
        print("\n⏳ Подключение к серверам Telegram...")
        await client.connect()

        if not await client.is_user_authorized():
            print("🚀 Запрос кода подтверждения...")
            print("💡 ВНИМАНИЕ: Код придет ВНУТРИ приложения Telegram (в чат 'Служебные уведомления').")
            print("   Если приложения нет, код придет в SMS (может занять до 2 минут).")

            try:
                # Используем start(), он сам запросит код в консоли
                await client.start(phone=PHONE)
            except PhoneNumberInvalidError:
                print(f"❌ Ошибка: Номер {PHONE} неверный. Проверьте формат в .env")
                return None

        print("\n✅ Сессия создана успешно!")
        print(f"   Файл сессии сохранен: {SESSION_FILE}")
        return client
        
    except SessionPasswordNeededError:
        print("\n🔐 У вас включена двухфакторная аутентификация (2FA).")
        password = input("Введите пароль (Cloud Password): ")
        await client.start(phone=PHONE, password=password)
        print("✅ Сессия создана с 2FA!")
        return client
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка при создании сессии: {e}")
        print("🔍 Рекомендация: Проверьте API_ID и API_HASH на https://my.telegram.org")
        return None


async def get_client():
    """
    Возвращает существующий клиент или создает новый.
    """
    if os.path.exists(SESSION_FILE):
        client = TelegramClient(SESSION_FILE, int(API_ID), API_HASH)
        
        try:
            await client.connect()
            if await client.is_user_authorized():
                return client
            else:
                print("⚠️ Сессия в файле устарела или не авторизована.")
                await client.disconnect()
                return await create_session()
        except Exception as e:
            print(f"⚠️ Ошибка подключения к существующей сессии: {e}")
            return await create_session()
    else:
        print("📄 Файл сессии не найден. Начинаем новую авторизацию.")
        return await create_session()


if __name__ == "__main__":
    import asyncio
    
    async def main():
        print("=== ТЕРИОН: Настройка шпиона (авторизация) ===")
        client = await get_client()
        if client:
            me = await client.get_me()
            print(f"\n🎉 Авторизация успешна! Вы вошли как: {me.first_name} (@{me.username or 'без_ника'})")
            print("Теперь вы можете запускать бота или шпиона.")
            await client.disconnect()
        else:
            print("\n❌ Не удалось завершить авторизацию.")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Отменено пользователем.")
