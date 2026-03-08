import asyncio
from telethon import TelegramClient

api_id = 30843855
api_hash = '87ee907282595722d00eb57a33aae2d3'

async def main():
    async with TelegramClient('scanbot', api_id, api_hash) as client:
        print("✅ Сессия создана успешно!")
        me = await client.get_me()
        print(me.stringify())

if __name__ == '__main__':
    asyncio.run(main())
