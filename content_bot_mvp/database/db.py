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

            # Таблица ботов и каналов для публикации (Обновлено по ТЗ №6)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS bots_channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bot_name TEXT NOT NULL,
                    bot_token TEXT NOT NULL,
                    tg_channel_id TEXT,
                    vk_group_id TEXT,
                    lead_group_id TEXT,
                    platform TEXT NOT NULL, -- TG, VK, BOTH
                    last_published TIMESTAMP,
                    status TEXT DEFAULT 'active',
                    is_archived BOOLEAN DEFAULT 0,
                    notes TEXT,
                    channel_alias TEXT,
                    brand TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Единицы контента (Content Items)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS content_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    body TEXT,
                    image_prompt TEXT,
                    image_url TEXT,
                    status TEXT DEFAULT 'idea', -- idea, draft, review, approved, scheduled, published
                    bot_name TEXT, -- Имя бота из bots_channels
                    cta_type TEXT,
                    cta_link TEXT,
                    created_by INTEGER,
                    approved_by INTEGER,
                    telegram_message_id TEXT,
                    hashtags TEXT,
                    quiz_link TEXT,
                    target_channel_alias TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (bot_name) REFERENCES bots_channels(bot_name)
                )
            """)

            # План публикаций (Content Plan)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS content_plan (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_item_id INTEGER,
                    scheduled_at DATETIME,
                    channel_id INTEGER,
                    published_at TIMESTAMP,
                    published BOOLEAN DEFAULT 0,
                    error_log TEXT,
                    target_channel_alias TEXT,
                    FOREIGN KEY (content_item_id) REFERENCES content_items(id)
                )
            """)

            # Дни рождения (Birthdays)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS birthdays (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    name TEXT,
                    birth_date DATE,
                    sent BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Лог аудита (Audit Log)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT,
                    bot_name TEXT,
                    channel_id INTEGER,
                    status TEXT,
                    user_id INTEGER,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await self.conn.commit()

    async def log_action(self, user_id: int, action: str, details: str = "", bot_name: str = None, channel_id: int = None, status: str = None):
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """INSERT INTO audit_log (user_id, action, details, bot_name, channel_id, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, action, details, bot_name, channel_id, status)
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

    async def get_bot_configs(self, bot_name: str):
        """Возвращает все активные конфигурации каналов для данного бота"""
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM bots_channels WHERE bot_name = ? AND status = 'active'", (bot_name,))
            return await cursor.fetchall()

    async def update_bot_status(self, bot_name: str, status: str):
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE bots_channels SET status = ?, updated_at = ? WHERE bot_name = ?",
                (status, datetime.now(), bot_name)
            )
            await self.conn.commit()

    async def add_bot_config(self, bot_name: str, token: str, tg_channel_id: str = None, vk_group_id: str = None,
                           lead_group_id: str = None, platform: str = "TG", is_archived: bool = False,
                           notes: str = None, channel_alias: str = None, brand: str = "TORION"):
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """INSERT OR REPLACE INTO bots_channels
                   (bot_name, bot_token, tg_channel_id, vk_group_id, lead_group_id, platform, is_archived, notes, channel_alias, brand)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (bot_name, token, tg_channel_id, vk_group_id, lead_group_id, platform, is_archived, notes, channel_alias, brand)
            )
            await self.conn.commit()

    async def update_item_status(self, item_id: int, status: str, user_id: int):
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE content_items SET status = ?, updated_at = ? WHERE id = ?",
                (status, datetime.now(), item_id)
            )
            await self.conn.commit()
            await self.log_action(user_id, f"status_change_{status}", f"Item ID: {item_id}", status=status)

# Singleton
db = ContentDatabase()
