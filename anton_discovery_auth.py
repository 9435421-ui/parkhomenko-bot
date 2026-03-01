"""
Минимальный скрипт авторизации Telethon
Создает файл anton_discovery.session для работы Discovery модуля
"""
from telethon import TelegramClient

# API credentials
API_ID = 39163454
API_HASH = '182611453d5822018d0772847a3f58a6'
SESSION_NAME = 'anton_discovery'

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
