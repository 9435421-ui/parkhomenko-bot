"""
База данных для хранения состояний пользователей и лидов
"""
import aiosqlite
import os
from typing import Optional, Dict, List
from datetime import datetime


class Database:
    """Класс для работы с SQLite базой данных"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_url = os.getenv("DATABASE_URL", "sqlite:///parkhomenko_bot.db")
            db_path = db_url.replace("sqlite:///", "")
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None
    
    async def connect(self):
        """Подключение к базе данных"""
        # Создаём директорию если не существует
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self._create_tables()
        print(f"✅ База данных подключена: {self.db_path}")
    
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
            
            # Таблица состояний пользователей
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
            
            # Таблица истории диалогов
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
            
            # Таблица лидов
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
                    source_bot TEXT DEFAULT 'qualification',
                    lead_type TEXT DEFAULT 'quiz',
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)

            # Единая таблица лидов для всех ботов (расширенная версия)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS unified_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    source_bot TEXT NOT NULL, -- 'qualification' или 'content'
                    lead_type TEXT, -- 'quiz', 'direct_request', 'report'
                    name TEXT,
                    username TEXT,
                    phone TEXT,
                    extra_contact TEXT,
                    details TEXT, -- JSON или текстовое описание (результаты квиза и т.д.)
                    status TEXT DEFAULT 'new',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sent_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            await self.conn.commit()
    
    # ============= ПОЛЬЗОВАТЕЛИ =============
    
    async def get_or_create_user(
        self,
        user_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> Dict:
        """Получить пользователя или создать нового"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                # Обновляем время последнего взаимодействия
                await cursor.execute(
                    "UPDATE users SET last_interaction = ? WHERE user_id = ?",
                    (datetime.now(), user_id)
                )
                await self.conn.commit()
                return dict(row)
            else:
                # Создаём нового пользователя
                await cursor.execute(
                    """INSERT INTO users (user_id, username, first_name, last_name)
                       VALUES (?, ?, ?, ?)""",
                    (user_id, username, first_name, last_name)
                )
                await self.conn.commit()
                
                await cursor.execute(
                    "SELECT * FROM users WHERE user_id = ?",
                    (user_id,)
                )
                row = await cursor.fetchone()
                return dict(row)
    
    # ============= СОСТОЯНИЯ =============
    
    async def get_user_state(self, user_id: int) -> Optional[Dict]:
        """Получить состояние пользователя"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT * FROM user_states WHERE user_id = ?",
                (user_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def update_user_state(self, user_id: int, **kwargs):
        """Обновить состояние пользователя"""
        async with self.conn.cursor() as cursor:
            # Проверяем существование записи
            await cursor.execute(
                "SELECT user_id FROM user_states WHERE user_id = ?",
                (user_id,)
            )
            exists = await cursor.fetchone()
            
            kwargs['updated_at'] = datetime.now()
            
            if exists:
                # Обновление
                set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
                values = list(kwargs.values()) + [user_id]
                await cursor.execute(
                    f"UPDATE user_states SET {set_clause} WHERE user_id = ?",
                    values
                )
            else:
                # Создание
                kwargs['user_id'] = user_id
                columns = ", ".join(kwargs.keys())
                placeholders = ", ".join(["?" for _ in kwargs])
                await cursor.execute(
                    f"INSERT INTO user_states ({columns}) VALUES ({placeholders})",
                    list(kwargs.values())
                )
            
            await self.conn.commit()
    
    async def reset_user_state(self, user_id: int):
        """Сброс состояния пользователя"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "DELETE FROM user_states WHERE user_id = ?",
                (user_id,)
            )
            await self.conn.commit()
    
    # ============= ИСТОРИЯ ДИАЛОГОВ =============
    
    async def add_dialog_message(
        self,
        user_id: int,
        role: str,
        message: str
    ):
        """Добавить сообщение в историю диалога"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """INSERT INTO dialog_history (user_id, role, message)
                   VALUES (?, ?, ?)""",
                (user_id, role, message)
            )
            await self.conn.commit()
    
    async def get_dialog_history(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[Dict]:
        """Получить историю диалога пользователя"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """SELECT role, message, created_at
                   FROM dialog_history
                   WHERE user_id = ?
                   ORDER BY created_at DESC
                   LIMIT ?""",
                (user_id, limit)
            )
            rows = await cursor.fetchall()
            # Возвращаем в хронологическом порядке
            return [dict(row) for row in reversed(rows)]
    
    async def clear_dialog_history(self, user_id: int):
        """Очистить историю диалога"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "DELETE FROM dialog_history WHERE user_id = ?",
                (user_id,)
            )
            await self.conn.commit()
    
    # ============= ЛИДЫ =============
    
    async def save_lead(
        self,
        user_id: int,
        name: str,
        phone: str,
        **kwargs
    ) -> int:
        """Сохранить лид в базу данных"""
        async with self.conn.cursor() as cursor:
            columns = ['user_id', 'name', 'phone'] + list(kwargs.keys())
            values = [user_id, name, phone] + list(kwargs.values())
            placeholders = ", ".join(["?" for _ in columns])
            
            await cursor.execute(
                f"""INSERT INTO leads ({', '.join(columns)})
                    VALUES ({placeholders})""",
                values
            )
            await self.conn.commit()
            return cursor.lastrowid

    async def upsert_unified_lead(
        self,
        user_id: int,
        source_bot: str,
        **kwargs
    ) -> int:
        """Обновить или добавить лид в единую таблицу"""
        async with self.conn.cursor() as cursor:
            # Проверяем наличие активного лида за последние 24 часа
            await cursor.execute(
                """SELECT id FROM unified_leads
                   WHERE user_id = ? AND source_bot = ?
                   AND created_at > datetime('now', '-1 day')
                   ORDER BY created_at DESC LIMIT 1""",
                (user_id, source_bot)
            )
            row = await cursor.fetchone()

            if row:
                lead_id = row[0]
                set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
                values = list(kwargs.values()) + [lead_id]
                await cursor.execute(
                    f"UPDATE unified_leads SET {set_clause} WHERE id = ?",
                    values
                )
                await self.conn.commit()
                return lead_id
            else:
                return await self.add_unified_lead(user_id, source_bot, phone=kwargs.get('phone', ''), **kwargs)

    async def add_unified_lead(
        self,
        user_id: int,
        source_bot: str,
        phone: str,
        name: Optional[str] = None,
        username: Optional[str] = None,
        lead_type: str = 'direct',
        details: Optional[str] = None,
        **kwargs
    ) -> int:
        """Добавить лид в единую таблицу"""
        async with self.conn.cursor() as cursor:
            columns = ['user_id', 'source_bot', 'phone', 'name', 'username', 'lead_type', 'details']
            values = [user_id, source_bot, phone, name, username, lead_type, details]

            for k, v in kwargs.items():
                if k not in columns:
                    columns.append(k)
                    values.append(v)

            placeholders = ", ".join(["?" for _ in columns])
            await cursor.execute(
                f"INSERT INTO unified_leads ({', '.join(columns)}) VALUES ({placeholders})",
                values
            )
            await self.conn.commit()
            return cursor.lastrowid
    
    async def get_leads(
        self,
        sent_to_group: Optional[bool] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Получить список лидов"""
        async with self.conn.cursor() as cursor:
            if sent_to_group is not None:
                await cursor.execute(
                    """SELECT * FROM leads
                       WHERE sent_to_group = ?
                       ORDER BY created_at DESC
                       LIMIT ?""",
                    (sent_to_group, limit)
                )
            else:
                await cursor.execute(
                    """SELECT * FROM leads
                       ORDER BY created_at DESC
                       LIMIT ?""",
                    (limit,)
                )
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def mark_lead_sent(self, lead_id: int):
        """Отметить лид как отправленный"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE leads SET sent_to_group = 1 WHERE id = ?",
                (lead_id,)
            )
            await self.conn.commit()


# Singleton instance
db = Database()
