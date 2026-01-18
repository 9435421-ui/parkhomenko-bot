import os
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.conn = None  # aiosqlite.Connection
        self.db_type = 'sqlite'  # Only SQLite for now

    async def connect(self):
        """Подключение к базе данных"""
        db_url = os.getenv("DATABASE_URL", "sqlite:///parkhomenko_bot.db")
        if not db_url:
            raise RuntimeError("DATABASE_URL must be set in .env")

        if not db_url.startswith('sqlite:///'):
            raise RuntimeError("Only SQLite is supported for now")

        import aiosqlite
        db_path = db_url.replace('sqlite:///', '')
        logger.info(f"🔄 Using SQLite database: {db_path}")
        self.conn = await aiosqlite.connect(db_path)
        # Enable foreign keys for SQLite
        await self.conn.execute("PRAGMA foreign_keys = ON")
        # Set row factory for dict-like access
        self.conn.row_factory = aiosqlite.Row

        # Создаём таблицы при подключении
        await self._create_tables()

    async def disconnect(self):
        """Отключение от базы данных"""
        if self.conn:
            await self.conn.close()

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

        async with self.conn.cursor() as cur:
            await cur.execute(leads_sql)
            await cur.execute(content_sql)
        await self.conn.commit()

    # Функции для работы с лидами
    async def save_lead(self, name, phone, extra_contact=None, object_type=None,
                       city=None, change_plan=None, bti_status=None):
        """Сохранить лид"""
        query = """
            INSERT INTO leads (name, phone, extra_contact, object_type, city, change_plan, bti_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        async with self.conn.cursor() as cur:
            await cur.execute(query, (name, phone, extra_contact, object_type,
                                    city, change_plan, bti_status))
        await self.conn.commit()

    # Функции для работы с контент-планом
    async def save_post(self, post_type, title, body, cta, publish_date):
        """Сохранить пост в контент-план"""
        query = """
            INSERT INTO content_plan (post_type, title, body, cta, publish_date, status)
            VALUES (?, ?, ?, ?, ?, 'draft')
        """
        async with self.conn.cursor() as cur:
            await cur.execute(query, (post_type, title, body, cta, publish_date.isoformat()))
            return cur.lastrowid
        await self.conn.commit()

    async def get_draft_posts(self):
        """Получить все посты со статусом draft"""
        query = """
            SELECT id, post_type, title, body, cta, publish_date, status, created_at
            FROM content_plan
            WHERE status='draft'
            ORDER BY created_at DESC
        """
        async with self.conn.cursor() as cur:
            await cur.execute(query)
            return await cur.fetchall()

    async def approve_post(self, post_id):
        """Утвердить пост"""
        query = "UPDATE content_plan SET status='approved' WHERE id=?"
        async with self.conn.cursor() as cur:
            await cur.execute(query, (post_id,))
        await self.conn.commit()

    async def delete_post(self, post_id):
        """Удалить пост"""
        query = "DELETE FROM content_plan WHERE id=?"
        async with self.conn.cursor() as cur:
            await cur.execute(query, (post_id,))
        await self.conn.commit()

    async def get_posts_to_publish(self):
        """Получить посты, готовые к публикации"""
        query = """
            SELECT id, post_type, title, body, cta, publish_date
            FROM content_plan
            WHERE status='approved' AND publish_date <= datetime('now')
            ORDER BY publish_date
        """
        async with self.conn.cursor() as cur:
            await cur.execute(query)
            return await cur.fetchall()

    async def mark_as_published(self, post_id):
        """Отметить пост как опубликованный"""
        query = "UPDATE content_plan SET status='published', published_at=datetime('now') WHERE id=?"
        async with self.conn.cursor() as cur:
            await cur.execute(query, (post_id,))
        await self.conn.commit()

    async def get_all_posts(self, limit=50):
        """Получить все посты для просмотра"""
        query = f"""
            SELECT id, post_type, title, body, cta, publish_date, status, created_at, published_at
            FROM content_plan
            ORDER BY created_at DESC
            LIMIT {limit}
        """
        async with self.conn.cursor() as cur:
            await cur.execute(query)
            return await cur.fetchall()

# Глобальный экземпляр базы данных
db = Database()
