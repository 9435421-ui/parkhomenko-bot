import asyncio
import aiosqlite
import os

async def migrate():
    db_path = 'parkhomenko_bot.db'
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return

    async with aiosqlite.connect(db_path) as db:
        # Check if columns exist in leads table
        cursor = await db.execute("PRAGMA table_info(leads)")
        columns = [row[1] for row in await cursor.fetchall()]

        if 'source' not in columns:
            print("Adding 'source' column to leads table...")
            await db.execute("ALTER TABLE leads ADD COLUMN source TEXT")

        if 'jk_info' not in columns:
            print("Adding 'jk_info' column to leads table...")
            await db.execute("ALTER TABLE leads ADD COLUMN jk_info TEXT")

        # Also add to subscribers table if needed for tracking
        cursor = await db.execute("PRAGMA table_info(subscribers)")
        columns = [row[1] for row in await cursor.fetchall()]

        if 'source' not in columns:
            print("Adding 'source' column to subscribers table...")
            await db.execute("ALTER TABLE subscribers ADD COLUMN source TEXT")

        await db.commit()
        print("Migration completed successfully.")

if __name__ == "__main__":
    asyncio.run(migrate())
