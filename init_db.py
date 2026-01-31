import asyncio
from content_bot_mvp.database.db import db
async def main():
    await db.connect()
    print("DB Initialized")
    await db.conn.close()
if __name__ == "__main__":
    asyncio.run(main())
