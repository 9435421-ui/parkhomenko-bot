import os
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.pool = None
        self.db_type = None  # 'postgresql' or 'sqlite'

    async def connect(self):
        """Подключение к базе данных"""
        db_url = os.getenv("DATABASE_URL", "sqlite:///parkhomenko_bot.db")
        if not db_url:
            raise RuntimeError("DATABASE_URL must be set in .env")

        # Detect database type
        if db_url.startswith('postgresql://'):
            self.db_type = 'postgresql'
            import asyncpg
            logger.info("🔄 Using PostgreSQL database")
            self.pool = await asyncpg.create_pool(db_url)
        elif db_url.startswith('sqlite:///'):
            self.db_type = 'sqlite'
            import aiosqlite
            db_path = db_url.replace('sqlite:///', '')
            logger.info(f"🔄 Using SQLite database: {db_path}")
            self.pool = await aiosqlite.connect(db_path)
            # Enable foreign keys for SQLite
            await self.pool.execute("PRAGMA foreign_keys = ON")
        else:
            raise RuntimeError(f"Unsupported database URL format: {db_url}")

        # Создаём таблицы при подключении
        await self._create_tables()

    async def disconnect(self):
        """Отключение от базы данных"""
        if self.pool:
            await self.pool.close()

    async def _create_tables(self):
        """Создание таблиц"""
        if self.db_type == 'sqlite':
            # SQLite syntax
            leads_sql = """
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    phone TEXT,
                    extra_contact TEXT,
                    object_type TEXT,
                    city TEXT,
                    change_plan TEXT,
                    bti_status TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """
            content_sql = """
                CREATE TABLE IF NOT EXISTS content_plan (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_type TEXT NOT NULL,
                    title TEXT,
                    body TEXT NOT NULL,
                    cta TEXT NOT NULL,
                    publish_date TEXT NOT NULL,
                    status TEXT DEFAULT 'draft',
                    created_at TEXT DEFAULT (datetime('now')),
                    published_at TEXT
                )
            """
        else:
            # PostgreSQL syntax
            leads_sql = """
                CREATE TABLE IF NOT EXISTS leads (
                    id SERIAL PRIMARY KEY,
                    name TEXT,
                    phone TEXT,
                    extra_contact TEXT,
                    object_type TEXT,
                    city TEXT,
                    change_plan TEXT,
                    bti_status TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """
            content_sql = """
                CREATE TABLE IF NOT EXISTS content_plan (
                    id SERIAL PRIMARY KEY,
                    post_type VARCHAR(20) NOT NULL,
                    title TEXT,
                    body TEXT NOT NULL,
                    cta TEXT NOT NULL,
                    publish_date TIMESTAMP NOT NULL,
                    status VARCHAR(20) DEFAULT 'draft',
                    created_at TIMESTAMP DEFAULT NOW(),
                    published_at TIMESTAMP
                )
            """

        async with self.pool.acquire() as conn:
            await conn.execute(leads_sql)
            await conn.execute(content_sql)

    # Функции для работы с лидами
    async def save_lead(self, name, phone, extra_contact=None, object_type=None,
                       city=None, change_plan=None, bti_status=None):
        """Сохранить лид"""
        async with self.pool.acquire() as conn:
            if self.db_type == 'sqlite':
                query = """
                    INSERT INTO leads (name, phone, extra_contact, object_type, city, change_plan, bti_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
            else:
                query = """
                    INSERT INTO leads (name, phone, extra_contact, object_type, city, change_plan, bti_status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """
            await conn.execute(query, name, phone, extra_contact, object_type,
                             city, change_plan, bti_status)

    # Функции для работы с контент-планом
    async def save_post(self, post_type, title, body, cta, publish_date):
        """Сохранить пост в контент-план"""
        async with self.pool.acquire() as conn:
            if self.db_type == 'sqlite':
                query = """
                    INSERT INTO content_plan (post_type, title, body, cta, publish_date, status)
                    VALUES (?, ?, ?, ?, ?, 'draft')
                """
                cursor = await conn.execute(query, post_type, title, body, cta, publish_date.isoformat())
                return cursor.lastrowid
            else:
                query = """
                    INSERT INTO content_plan (post_type, title, body, cta, publish_date, status)
                    VALUES ($1, $2, $3, $4, $5, 'draft')
                    RETURNING id
                """
                return await conn.fetchval(query, post_type, title, body, cta, publish_date)

    async def get_draft_posts(self):
        """Получить все посты со статусом draft"""
        async with self.pool.acquire() as conn:
            query = """
                SELECT id, post_type, title, body, cta, publish_date, status, created_at
                FROM content_plan
                WHERE status='draft'
                ORDER BY created_at DESC
            """
            result = await conn.execute(query)
            if self.db_type == 'sqlite':
                return await result.fetchall()
            else:
                return result

    async def approve_post(self, post_id):
        """Утвердить пост"""
        async with self.pool.acquire() as conn:
            if self.db_type == 'sqlite':
                query = "UPDATE content_plan SET status='approved' WHERE id=?"
            else:
                query = "UPDATE content_plan SET status='approved' WHERE id=$1"
            await conn.execute(query, post_id)

    async def delete_post(self, post_id):
        """Удалить пост"""
        async with self.pool.acquire() as conn:
            if self.db_type == 'sqlite':
                query = "DELETE FROM content_plan WHERE id=?"
            else:
                query = "DELETE FROM content_plan WHERE id=$1"
            await conn.execute(query, post_id)

    async def get_posts_to_publish(self):
        """Получить посты, готовые к публикации"""
        async with self.pool.acquire() as conn:
            if self.db_type == 'sqlite':
                query = """
                    SELECT id, post_type, title, body, cta, publish_date
                    FROM content_plan
                    WHERE status='approved' AND publish_date <= datetime('now')
                    ORDER BY publish_date
                """
            else:
                query = """
                    SELECT id, post_type, title, body, cta, publish_date
                    FROM content_plan
                    WHERE status='approved' AND publish_date <= NOW()
                    ORDER BY publish_date
                """
            result = await conn.execute(query)
            if self.db_type == 'sqlite':
                return await result.fetchall()
            else:
                return result

    async def mark_as_published(self, post_id):
        """Отметить пост как опубликованный"""
        async with self.pool.acquire() as conn:
            if self.db_type == 'sqlite':
                query = "UPDATE content_plan SET status='published', published_at=datetime('now') WHERE id=?"
            else:
                query = "UPDATE content_plan SET status='published', published_at=NOW() WHERE id=$1"
            await conn.execute(query, post_id)

    async def get_all_posts(self, limit=50):
        """Получить все посты для просмотра"""
        async with self.pool.acquire() as conn:
            if self.db_type == 'sqlite':
                query = f"""
                    SELECT id, post_type, title, body, cta, publish_date, status, created_at, published_at
                    FROM content_plan
                    ORDER BY created_at DESC
                    LIMIT {limit}
                """
            else:
                query = """
                    SELECT id, post_type, title, body, cta, publish_date, status, created_at, published_at
                    FROM content_plan
                    ORDER BY created_at DESC
                    LIMIT $1
                """
            if self.db_type == 'sqlite':
                result = await conn.execute(query)
                return await result.fetchall()
            else:
                return await conn.fetch(query, limit)

# Глобальный экземпляр базы данных
db = Database()
