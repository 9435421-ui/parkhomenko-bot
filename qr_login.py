import asyncio
import os
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

async def main():
    # Используем наше единое имя сессии
    client = TelegramClient('anton_parser', int(os.getenv('API_ID')), os.getenv('API_HASH'))
    await client.connect()

    print("\n--- ГЕНЕРАЦИЯ QR-КОДА ---")
    qr = await client.qr_login()

    print("\n1. Откройте Telegram на телефоне")
    print("2. Настройки -> Устройства -> Подключить устройство")
    print("3. Перейдите по ссылке ниже и отсканируйте QR (или введите её в браузере):")
    print(f"\n👉 {qr.url}\n")

    try:
        # Ждем 60 секунд, пока вы сканируете
        await qr.wait(60)
        me = await client.get_me()
        print(f"\n✅ УСПЕХ! Авторизован как: {me.first_name}")
    except Exception as e:
        print(f"\n❌ Ошибка или время истекло: {e}")
    finally:
        await client.disconnect()

asyncio.run(main())
