import aiosqlite
import os
from datetime import datetime
from typing import List, Dict, Optional

class ContentDatabase:
    def __init__(self, db_path: str = "content_bot_mvp/database/content.db"):
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self._create_tables()
        print(f"✅ Content Database connected: {self.db_path}")

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def _create_tables(self):
        async with self.conn.cursor() as cursor:
            # Table for content plan
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS content_plan (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT,
                    title TEXT,
                    body TEXT NOT NULL,
                    cta_link TEXT,
                    image_description TEXT,
                    status TEXT DEFAULT 'draft',
                    publish_date TIMESTAMP,
                    target_channel_alias TEXT,
                    brand TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    published_at TIMESTAMP
                )
            """)

            # Table for audit log
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    bot_name TEXT,
                    channel_id TEXT,
                    status TEXT,
                    user_id INTEGER,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Table for bots and channels configuration
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS bots_channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_name TEXT NOT NULL,
                    channel_alias TEXT NOT NULL,
                    channel_id TEXT NOT NULL,
                    brand TEXT NOT NULL
                )
            """)

            # Initial seed for bots_channels if empty
            await cursor.execute("SELECT COUNT(*) FROM bots_channels")
            count = (await cursor.fetchone())[0]
            if count == 0:
                channels = [
                    ('domGrad_bot', '@torion_channel', '-1002345678901', 'Torion'),
                    ('domGrad_bot', '@pereplanirovka_stroitelstvo', '-1003456789012', 'DomGrand')
                ]
                await cursor.executemany(
                    "INSERT INTO bots_channels (bot_name, channel_alias, channel_id, brand) VALUES (?, ?, ?, ?)",
                    channels
                )

            await self.conn.commit()

    async def save_post(self, **kwargs) -> int:
        async with self.conn.cursor() as cursor:
            columns = kwargs.keys()
            placeholders = ", ".join(["?" for _ in columns])
            query = f"INSERT INTO content_plan ({', '.join(columns)}) VALUES ({placeholders})"
            await cursor.execute(query, list(kwargs.values()))
            await self.conn.commit()
            return cursor.lastrowid

    async def update_post(self, post_id: int, **kwargs):
        async with self.conn.cursor() as cursor:
            set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
            query = f"UPDATE content_plan SET {set_clause} WHERE id = ?"
            await cursor.execute(query, list(kwargs.values()) + [post_id])
            await self.conn.commit()

    async def get_post(self, post_id: int) -> Optional[Dict]:
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM content_plan WHERE id = ?", (post_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_posts_by_status(self, status: str) -> List[Dict]:
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM content_plan WHERE status = ? ORDER BY created_at DESC", (status,))
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_scheduled_posts(self) -> List[Dict]:
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT * FROM content_plan WHERE status = 'scheduled' AND publish_date <= CURRENT_TIMESTAMP"
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def add_audit_log(self, action: str, **kwargs):
        async with self.conn.cursor() as cursor:
            kwargs['action'] = action
            columns = kwargs.keys()
            placeholders = ", ".join(["?" for _ in columns])
            query = f"INSERT INTO audit_log ({', '.join(columns)}) VALUES ({placeholders})"
            await cursor.execute(query, list(kwargs.values()))
            await self.conn.commit()

    async def get_bots_channels(self) -> List[Dict]:
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM bots_channels")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_channel_config(self, channel_alias: str) -> Optional[Dict]:
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM bots_channels WHERE channel_alias = ?", (channel_alias,))
            row = await cursor.fetchone()
            return dict(row) if row else None

db = ContentDatabase()
