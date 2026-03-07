"""
Минимальный скрипт авторизации Telethon
Создает файл anton_parser.session для работы Discovery модуля
"""
import os
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

# API credentials
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION_NAME = 'anton_parser'

async def main():
    print("🚀 Запуск авторизации Telethon...")
    print("Создается сессия:", SESSION_NAME + ".session")
    
    # Создаем клиент
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    
    # Авторизация (запросит номер телефона и код)
    await client.start()
    
    # Проверяем авторизацию
    me = await client.get_me()
    print(f"✅ Авторизация успешна!")
    print(f"👤 Пользователь: {me.first_name} (@{me.username})")
    print(f"📱 ID: {me.id}")
    print(f"💾 Файл сессии сохранен: {SESSION_NAME}.session")
    
    # Закрываем соединение
    await client.disconnect()
    print("\n🎉 Готово! Можно использовать сессию для Discovery.")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
