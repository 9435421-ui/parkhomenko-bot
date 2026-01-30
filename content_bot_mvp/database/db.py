import aiosqlite
import os
from datetime import datetime
from typing import List, Dict, Optional

class ContentDatabase:
    def __init__(self, db_path: str = "content_bot_mvp/database/content.db"):
        self.db_path = db_path

    async def connect(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self._create_tables()

    async def _create_tables(self):
        async with self.conn.cursor() as cursor:
            # Пользователи и роли
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE,
                    username TEXT,
                    role TEXT DEFAULT 'VIEWER', -- ADMIN, EDITOR, VIEWER
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Каналы публикации
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id INTEGER UNIQUE,
                    title TEXT,
                    channel_type TEXT, -- main, agent
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Контент-план
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS content_plan (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    theme TEXT,
                    post_type TEXT, -- expert, educational, sales, engaging
                    target_date DATE,
                    status TEXT DEFAULT 'planned', -- planned, in_progress, completed
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Посты
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER,
                    channel_id INTEGER,
                    text TEXT,
                    image_prompt TEXT,
                    image_url TEXT,
                    status TEXT DEFAULT 'draft', -- draft, pending, approved, published
                    created_by INTEGER,
                    approved_by INTEGER,
                    published_at TIMESTAMP,
                    source_tag TEXT DEFAULT 'content_bot',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (plan_id) REFERENCES content_plan(id),
                    FOREIGN KEY (channel_id) REFERENCES channels(id)
                )
            """)

            # Лог аудита
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action TEXT,
                    target_type TEXT, -- post, plan, user
                    target_id INTEGER,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await self.conn.commit()

    async def log_action(self, user_id: int, action: str, target_type: str, target_id: int, details: str = ""):
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO audit_log (user_id, action, target_type, target_id, details) VALUES (?, ?, ?, ?, ?)",
                (user_id, action, target_type, target_id, details)
            )
            await self.conn.commit()

    async def get_user(self, telegram_id: int):
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
            return await cursor.fetchone()

    async def add_user(self, telegram_id: int, username: str, role: str = 'VIEWER'):
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "INSERT OR IGNORE INTO users (telegram_id, username, role) VALUES (?, ?, ?)",
                (telegram_id, username, role)
            )
            await self.conn.commit()

# Singleton
db = ContentDatabase()
