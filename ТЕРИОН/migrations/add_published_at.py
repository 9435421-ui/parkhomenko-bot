import aiosqlite
import asyncio

async def migrate():
    """Добавить колонку published_at в content_plan"""
    async with aiosqlite.connect('parkhomenko_bot.db') as db:
        # Проверить, существует ли колонка
        cursor = await db.execute("PRAGMA table_info(content_plan)")
        columns = [row[1] for row in await cursor.fetchall()]

        if 'published_at' in columns:
            print("✅ Колонка published_at уже существует")
            return

        await db.execute("""
            ALTER TABLE content_plan
            ADD COLUMN published_at TEXT
        """)
        await db.commit()
        print("✅ Колонка published_at добавлена")

if __name__ == '__main__':
    asyncio.run(migrate())
