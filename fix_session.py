from telethon import TelegramClient
import asyncio

# Ваши верные данные
api_id = 39163454
api_hash = '182611453d5822018d0772847a3f58a6'
phone = '+79629435421'

async def main():
    client = TelegramClient('anton_discovery', api_id, api_hash)
    await client.start(phone=phone)
    print("✅ СЕССИЯ УСПЕШНО СОЗДАНА!")
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
