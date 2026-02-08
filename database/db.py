"""
База данных для хранения состояний пользователей и лидов
"""
import aiosqlite
import os
from typing import Optional, Dict, List
from datetime import datetime


class Database:
    """Класс для работы с SQLite базой данных"""
    
    def __init__(self, db_path: str = "database/bot.db"):
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        """Подключение к базе данных"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self._create_tables()
        print(f"✅ База данных подключена: {self.db_path}")
    
    async def close(self):
        if self.conn:
            await self.conn.close()
    
    async def _create_tables(self):
        """Создание необходимых таблиц"""
        async with self.conn.cursor() as cursor:
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
            
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_states (
                    user_id INTEGER PRIMARY KEY,
                    mode TEXT,
                    quiz_step INTEGER DEFAULT 0,
                    name TEXT,
                    phone TEXT,
                    extra_contact TEXT,
                    object_type TEXT,
                    city TEXT,
                    floor TEXT,
                    total_floors TEXT,
                    remodeling_status TEXT,
                    change_plan TEXT,
                    bti_status TEXT,
                    consent_given BOOLEAN DEFAULT 0,
                    contact_received BOOLEAN DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS dialog_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    role TEXT,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    name TEXT,
                    phone TEXT,
                    extra_contact TEXT,
                    object_type TEXT,
                    city TEXT,
                    floor TEXT,
                    total_floors TEXT,
                    remodeling_status TEXT,
                    change_plan TEXT,
                    bti_status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sent_to_group BOOLEAN DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS content_plan (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    channel TEXT DEFAULT 'terion',
                    title TEXT,
                    body TEXT NOT NULL,
                    cta TEXT,
                    theme TEXT,
                    publish_date TIMESTAMP,
                    status TEXT DEFAULT 'draft',
                    image_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await self.conn.commit()
    
    async def get_or_create_user(self, user_id: int, username: Optional[str] = None,
                                first_name: Optional[str] = None, last_name: Optional[str] = None) -> Dict:
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            
            if row:
                await cursor.execute("UPDATE users SET last_interaction = ? WHERE user_id = ?", (datetime.now(), user_id))
                await self.conn.commit()
                return dict(row)
            else:
                await cursor.execute(
                    "INSERT INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
                    (user_id, username, first_name, last_name)
                )
                await self.conn.commit()
                await cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                return dict(await cursor.fetchone())
    
    async def get_user_state(self, user_id: int) -> Optional[Dict]:
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM user_states WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def update_user_state(self, user_id: int, **kwargs):
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT user_id FROM user_states WHERE user_id = ?", (user_id,))
            exists = await cursor.fetchone()
            
            kwargs['updated_at'] = datetime.now()
            
            if exists:
                set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
                values = list(kwargs.values()) + [user_id]
                await cursor.execute(f"UPDATE user_states SET {set_clause} WHERE user_id = ?", values)
            else:
                kwargs['user_id'] = user_id
                columns = ", ".join(kwargs.keys())
                placeholders = ", ".join(["?" for _ in kwargs])
                await cursor.execute(f"INSERT INTO user_states ({columns}) VALUES ({placeholders})", list(kwargs.values()))
            
            await self.conn.commit()
    
    async def reset_user_state(self, user_id: int):
        async with self.conn.cursor() as cursor:
            await cursor.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
            await self.conn.commit()
    
    async def add_dialog_message(self, user_id: int, role: str, message: str):
        async with self.conn.cursor() as cursor:
            await cursor.execute("INSERT INTO dialog_history (user_id, role, message) VALUES (?, ?, ?)",
                                (user_id, role, message))
            await self.conn.commit()
    
    async def get_dialog_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT role, message, created_at FROM dialog_history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in reversed(rows)]
    
    async def save_lead(self, user_id: int, name: str, phone: str, **kwargs) -> int:
        async with self.conn.cursor() as cursor:
            columns = ['user_id', 'name', 'phone'] + list(kwargs.keys())
            values = [user_id, name, phone] + list(kwargs.values())
            await cursor.execute(f"INSERT INTO leads ({', '.join(columns)}) VALUES ({', '.join(['?' for _ in columns])})", values)
            await self.conn.commit()
            return cursor.lastrowid
    
    async def get_leads(self, sent_to_group: Optional[bool] = None, limit: int = 100) -> List[Dict]:
        async with self.conn.cursor() as cursor:
            if sent_to_group is not None:
                await cursor.execute("SELECT * FROM leads WHERE sent_to_group = ? ORDER BY created_at DESC LIMIT ?",
                                    (sent_to_group, limit))
            else:
                await cursor.execute("SELECT * FROM leads ORDER BY created_at DESC LIMIT ?", (limit,))
            return [dict(row) for row in await cursor.fetchall()]
    
    async def mark_lead_sent(self, lead_id: int):
        async with self.conn.cursor() as cursor:
            await cursor.execute("UPDATE leads SET sent_to_group = 1 WHERE id = ?", (lead_id,))
            await self.conn.commit()

    async def save_post(self, post_type: str, title: str, body: str, cta: str, publish_date: datetime,
                       channel: str = 'terion', theme: Optional[str] = None, image_url: Optional[str] = None) -> int:
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """INSERT INTO content_plan (type, channel, title, body, cta, theme, publish_date, image_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (post_type, channel, title, body, cta, theme, publish_date, image_url)
            )
            await self.conn.commit()
            return cursor.lastrowid

    async def get_draft_posts(self) -> List[Dict]:
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM content_plan WHERE status = 'draft' ORDER BY created_at DESC")
            return [dict(row) for row in await cursor.fetchall()]

    async def get_posts_to_publish(self) -> List[Dict]:
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT * FROM content_plan WHERE status = 'approved' AND publish_date <= ? ORDER BY publish_date ASC",
                (datetime.now(),)
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def mark_as_published(self, post_id: int):
        async with self.conn.cursor() as cursor:
            await cursor.execute("UPDATE content_plan SET status = 'published' WHERE id = ?", (post_id,))
            await self.conn.commit()

    async def update_content_plan_entry(self, post_id: int, **kwargs):
        async with self.conn.cursor() as cursor:
            set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
            values = list(kwargs.values()) + [post_id]
            await cursor.execute(f"UPDATE content_plan SET {set_clause} WHERE id = ?", values)
            await self.conn.commit()

    async def delete_post(self, post_id: int):
        async with self.conn.cursor() as cursor:
            await cursor.execute("DELETE FROM content_plan WHERE id = ?", (post_id,))
            await self.conn.commit()

    async def get_max_publish_date(self, status: str = 'approved') -> Optional[datetime]:
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT MAX(publish_date) FROM content_plan WHERE status = ?", (status,))
            row = await cursor.fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0])
            return None


db = Database()
