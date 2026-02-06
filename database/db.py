"""
База данных для хранения состояний пользователей, лидов и контент-плана
"""
import aiosqlite
import os
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class Database:
    """Класс для работы с SQLite базой данных"""
    
    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or os.getenv("DATABASE_URL", "sqlite:///parkhomenko_bot.db")
        self.db_path = self.db_url.replace('sqlite:///', '')
        self.conn: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        """Подключение к базе данных"""
        os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else ".", exist_ok=True)
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA foreign_keys = ON")
        await self._create_tables()
        logger.info(f"✅ База данных подключена: {self.db_path}")
    
    async def close(self):
        """Закрытие соединения с базой данных"""
        if self.conn:
            await self.conn.close()
    
    async def _create_tables(self):
        """Создание необходимых таблиц"""
        async with self.conn.cursor() as cursor:
            # Таблица пользователей
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    phone TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица лидов
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    name TEXT,
                    phone TEXT,
                    city TEXT,
                    object_type TEXT,
                    floor TEXT,
                    area TEXT,
                    remodeling_status TEXT,
                    description TEXT,
                    bti_file TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица контент-плана
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS content_plan (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    title TEXT,
                    body TEXT NOT NULL,
                    cta TEXT NOT NULL,
                    content_hash TEXT UNIQUE,
                    media_data TEXT,
                    publish_date TEXT NOT NULL,
                    status TEXT DEFAULT 'draft',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    published_at TIMESTAMP
                )
            """)
            await self.conn.commit()

    async def save_lead(self, user_id: int, data: Dict[str, Any]):
        """Сохранить или обновить лид"""
        columns = ['user_id'] + list(data.keys())
        placeholders = ", ".join(["?" for _ in columns])
        values = [user_id] + list(data.values())

        async with self.conn.cursor() as cursor:
            await cursor.execute(
                f"INSERT INTO leads ({', '.join(columns)}) VALUES ({placeholders})",
                values
            )
            await self.conn.commit()
            return cursor.lastrowid

    async def update_lead(self, user_id: int, data: Dict[str, Any]):
        """Обновить последний лид пользователя (для совместимости)"""
        if not data: return

        set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
        values = list(data.values()) + [user_id]

        async with self.conn.cursor() as cursor:
            # Находим последний ID лида этого пользователя
            await cursor.execute("SELECT id FROM leads WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
            row = await cursor.fetchone()
            if row:
                lead_id = row[0]
                await cursor.execute(f"UPDATE leads SET {set_clause} WHERE id = ?", list(data.values()) + [lead_id])
                await self.conn.commit()
            else:
                # Если лида нет, создаем новый
                await self.save_lead(user_id, data)

    async def get_user_state(self, user_id: int) -> Dict[str, Any]:
        """Получить данные пользователя из таблицы users"""
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            return dict(row) if row else {}

    async def update_user_state(self, user_id: int, **kwargs):
        """Обновить данные/состояние пользователя в таблице users"""
        if not kwargs: return

        # Сначала проверяем существование
        state = await self.get_user_state(user_id)
        if not state:
            # Создаем
            cols = ["user_id"] + list(kwargs.keys())
            vals = [user_id] + list(kwargs.values())
            placeholders = ", ".join(["?" for _ in cols])
            await self.conn.execute(f"INSERT INTO users ({', '.join(cols)}) VALUES ({placeholders})", vals)
        else:
            # Обновляем
            set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
            vals = list(kwargs.values()) + [user_id]
            await self.conn.execute(f"UPDATE users SET {set_clause}, last_interaction = CURRENT_TIMESTAMP WHERE user_id = ?", vals)

        await self.conn.commit()

# Singleton instance
db = Database()
