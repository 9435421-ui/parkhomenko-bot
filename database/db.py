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
                    area TEXT,
                    remodeling_status TEXT,
                    change_plan TEXT,
                    bti_status TEXT,
                    extra_questions TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sent_to_group BOOLEAN DEFAULT 0,
                    thread_id INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            for col, ctype in [("area", "TEXT"), ("extra_questions", "TEXT"), ("thread_id", "INTEGER")]:
                try:
                    await cursor.execute(f"ALTER TABLE leads ADD COLUMN {col} {ctype}")
                except Exception:
                    pass

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
                    admin_id INTEGER DEFAULT NULL,
                    published_at TIMESTAMP DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица для дней рождения клиентов
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS clients_birthdays (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT,
                    birth_date DATE NOT NULL,
                    channel TEXT DEFAULT 'telegram',
                    greeting_sent BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            # Таблица целевых ресурсов для мониторинга (TG чаты + VK группы)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS target_resources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL CHECK(type IN ('telegram', 'vk')),
                    link TEXT NOT NULL UNIQUE,
                    title TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    last_post_id INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица ключевых слов для мониторинга
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS spy_keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT NOT NULL UNIQUE,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Настройки бота (key-value для переключателей и т.п.)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS bot_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await cursor.execute(
                "INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('spy_notify_enabled', '1')"
            )

            # Таблица лидов от шпиона (TG/VK: автор, ссылка на профиль, текст)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS spy_leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    author_id TEXT,
                    username TEXT,
                    profile_url TEXT,
                    text TEXT,
                    url TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица истории контента (финансовый трекинг)
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS content_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_text TEXT,
                    image_url TEXT,
                    model_used VARCHAR(50),
                    cost_rub DECIMAL(10, 2),
                    platform VARCHAR(20),
                    channel VARCHAR(50),
                    post_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_archived BOOLEAN DEFAULT FALSE
                )
            """)
            await self.conn.commit()

            # Миграция: колонка contacted_at для «Продавца» (первый диалог с лидом)
            try:
                await cursor.execute("ALTER TABLE spy_leads ADD COLUMN contacted_at TIMESTAMP NULL")
                await self.conn.commit()
            except Exception:
                pass  # колонка уже есть

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
    
    # Разрешённые поля для update_user_state (whitelist)
    ALLOWED_USER_STATE_FIELDS = {
        'mode', 'quiz_step', 'name', 'phone', 'extra_contact',
        'object_type', 'city', 'floor', 'total_floors',
        'remodeling_status', 'change_plan', 'bti_status',
        'consent_given', 'contact_received', 'updated_at'
    }

    async def update_user_state(self, user_id: int, **kwargs):
        """Обновить состояние пользователя с whitelist защитой от SQL-инъекций"""
        # Фильтруем только разрешённые поля
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in self.ALLOWED_USER_STATE_FIELDS}
        
        if not filtered_kwargs:
            return  # Нечего обновлять
        
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT user_id FROM user_states WHERE user_id = ?", (user_id,))
            exists = await cursor.fetchone()
            
            filtered_kwargs['updated_at'] = datetime.now()
            
            if exists:
                set_clause = ", ".join([f"{k} = ?" for k in filtered_kwargs.keys()])
                values = list(filtered_kwargs.values()) + [user_id]
                await cursor.execute(f"UPDATE user_states SET {set_clause} WHERE user_id = ?", values)
            else:
                filtered_kwargs['user_id'] = user_id
                columns = ", ".join(filtered_kwargs.keys())
                placeholders = ", ".join(["?" for _ in filtered_kwargs])
                await cursor.execute(f"INSERT INTO user_states ({columns}) VALUES ({placeholders})", list(filtered_kwargs.values()))
            
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
    
    async def add_lead(self, user_id: int, name: str, phone: str, **kwargs) -> int:
        """Добавить лида в БД"""
        async with self.conn.cursor() as cursor:
            columns = ['user_id', 'name', 'phone'] + list(kwargs.keys())
            values = [user_id, name, phone] + list(kwargs.values())
            await cursor.execute(
                f"INSERT INTO leads ({', '.join(columns)}) VALUES ({', '.join(['?' for _ in columns])})",
                values
            )
            await self.conn.commit()
            return cursor.lastrowid
    
    async def update_lead_status(self, user_id: int, status: str, data: Dict = None):
        """Обновить статус лида"""
        async with self.conn.cursor() as cursor:
            # Находим последнего лида пользователя
            await cursor.execute(
                "SELECT id FROM leads WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
                (user_id,)
            )
            row = await cursor.fetchone()
            
            if row:
                lead_id = row['id']
                if data:
                    set_clause = ", ".join([f"{k} = ?" for k in data.keys()])
                    values = list(data.values()) + [lead_id]
                    await cursor.execute(f"UPDATE leads SET {set_clause} WHERE id = ?", values)
                
                await cursor.execute("UPDATE leads SET sent_to_group = 1 WHERE id = ?", (lead_id,))
                await self.conn.commit()
    
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

    async def update_lead_extra(self, lead_id: int, extra_text: str, append: bool = True):
        """Дополнение к заявке (одна заявка): дополнительные вопросы/документы."""
        async with self.conn.cursor() as cursor:
            if append:
                await cursor.execute("SELECT extra_questions FROM leads WHERE id = ?", (lead_id,))
                row = await cursor.fetchone()
                old = (row["extra_questions"] or "") if row else ""
                new_val = (old + "\n---\n" + extra_text) if old else extra_text
            else:
                new_val = extra_text
            await cursor.execute("UPDATE leads SET extra_questions = ? WHERE id = ?", (new_val, lead_id))
            await self.conn.commit()

    async def set_lead_thread(self, lead_id: int, thread_id: int):
        async with self.conn.cursor() as cursor:
            await cursor.execute("UPDATE leads SET thread_id = ? WHERE id = ?", (thread_id, lead_id))
            await self.conn.commit()

    # === ЛИДЫ ОТ ШПИОНА (spy_leads) ===
    async def add_spy_lead(
        self,
        source_type: str,
        source_name: str,
        url: str,
        text: str = "",
        author_id: Optional[str] = None,
        username: Optional[str] = None,
        profile_url: Optional[str] = None,
    ) -> int:
        """Сохранить лид от шпиона: источник, автор, ссылка на профиль, текст."""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """INSERT INTO spy_leads (source_type, source_name, author_id, username, profile_url, text, url)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (source_type, source_name, author_id or None, username or None, profile_url or None, text or "", url),
            )
            await self.conn.commit()
            return cursor.lastrowid

    async def get_spy_leads_count_24h(self) -> int:
        """Количество лидов от шпиона за последние 24 часа."""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT COUNT(*) FROM spy_leads WHERE created_at >= datetime('now', '-1 day')",
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_recent_spy_leads(self, limit: int = 30) -> List[Dict]:
        """Последние лиды от шпиона (для генерации идей контента)."""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT id, source_type, source_name, text, url, created_at FROM spy_leads ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_spy_leads_since_hours(self, since_hours: int = 12) -> List[Dict]:
        """Лиды за последние N часов (ревизия: кто попался, какие боли)."""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """SELECT id, source_type, source_name, author_id, username, profile_url, text, url, created_at
                   FROM spy_leads WHERE created_at >= datetime('now', ?)
                   ORDER BY created_at DESC""",
                (f"-{since_hours} hours",),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_spy_lead_uncontacted_by_author(self, author_id: str) -> Optional[Dict]:
        """Необработанный лид по author_id (для первого контакта «Продавец»). author_id — строка (TG user id)."""
        if not author_id:
            return None
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """SELECT id, source_name, text, created_at FROM spy_leads
                   WHERE (author_id = ? OR author_id = ?) AND (contacted_at IS NULL)
                   ORDER BY created_at DESC LIMIT 1""",
                (str(author_id), author_id),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def mark_spy_lead_contacted(self, lead_id: int) -> None:
        """Отметить лид как «с ним уже начали диалог» (Антон написал первым)."""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE spy_leads SET contacted_at = datetime('now') WHERE id = ?",
                (lead_id,),
            )
            await self.conn.commit()

    async def get_setting(self, key: str, default: str = "") -> str:
        """Получить значение настройки (bot_settings)."""
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT value FROM bot_settings WHERE key = ?", (key,))
            row = await cursor.fetchone()
            return row[0] if row else default

    async def set_setting(self, key: str, value: str) -> None:
        """Установить значение настройки (bot_settings)."""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "INSERT OR REPLACE INTO bot_settings (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, datetime.now()),
            )
            await self.conn.commit()

    async def save_post(self, post_type: str, title: str, body: str, cta: str, publish_date: datetime,
                       channel: str = 'terion', theme: Optional[str] = None, 
                       image_url: Optional[str] = None, admin_id: Optional[int] = None,
                       status: str = 'draft') -> int:
        """Сохранить пост в контент-план"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """INSERT INTO content_plan (type, channel, title, body, cta, theme, publish_date, image_url, admin_id, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (post_type, channel, title, body, cta, theme, publish_date, image_url, admin_id, status)
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

    # Разрешённые поля для update_content_plan_entry (whitelist)
    ALLOWED_CONTENT_PLAN_FIELDS = {
        'type', 'channel', 'title', 'body', 'cta', 'theme',
        'publish_date', 'status', 'image_url', 'admin_id', 'published_at'
    }

    async def update_content_plan_entry(self, post_id: int, **kwargs):
        """Обновить запись контент-плана с whitelist защитой от SQL-инъекций"""
        # Фильтруем только разрешённые поля
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in self.ALLOWED_CONTENT_PLAN_FIELDS}
        
        if not filtered_kwargs:
            return  # Нечего обновлять
        
        async with self.conn.cursor() as cursor:
            set_clause = ", ".join([f"{k} = ?" for k in filtered_kwargs.keys()])
            values = list(filtered_kwargs.values()) + [post_id]
            await cursor.execute(f"UPDATE content_plan SET {set_clause} WHERE id = ?", values)
            await self.conn.commit()

    async def delete_post(self, post_id: int):
        async with self.conn.cursor() as cursor:
            await cursor.execute("DELETE FROM content_plan WHERE id = ?", (post_id,))
            await self.conn.commit()

    # Алиас для совместимости с handlers/content.py
    async def add_content_post(self, title: str, body: str, cta: str, channel: str = "draft",
                              scheduled_date: datetime = None, **kwargs) -> int:
        """Алиас для save_post — добавить пост в контент-план. По умолчанию время публикации 12:00."""
        default_time = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
        return await self.save_post(
            post_type=kwargs.get("type", "post"),
            title=title,
            body=body,
            cta=cta,
            channel=channel,
            publish_date=scheduled_date or default_time,
            theme=kwargs.get("theme"),
            image_url=kwargs.get("image_url"),
            admin_id=kwargs.get("admin_id"),
            status=kwargs.get("status", "draft")
        )

    async def update_content_post(self, post_id: int, **kwargs):
        """Алиас — обновить пост"""
        if "status" in kwargs:
            await self.mark_as_published(post_id)
        else:
            await self.update_content_plan_entry(post_id, **kwargs)

    async def get_content_post(self, post_id: int):
        """Получить пост по ID"""
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT * FROM content_plan WHERE id = ?", (post_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_max_publish_date(self, status: str = 'approved') -> Optional[datetime]:
        async with self.conn.cursor() as cursor:
            await cursor.execute("SELECT MAX(publish_date) FROM content_plan WHERE status = ?", (status,))
            row = await cursor.fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0])
            return None
    
    # === ДНИ РОЖДЕНИЯ ===
    async def add_client_birthday(self, user_id: int, name: str, birth_date: str, channel: str = 'telegram'):
        """Добавить дату рождения клиента"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO clients_birthdays (user_id, name, birth_date, channel) VALUES (?, ?, ?, ?)",
                (user_id, name, birth_date, channel)
            )
            await self.conn.commit()
            return cursor.lastrowid
    
    async def get_today_birthdays(self) -> List[Dict]:
        """Получить клиентов с ДР сегодня"""
        today = datetime.now().strftime("%m-%d")
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT * FROM clients_birthdays WHERE strftime('%m-%d', birth_date) = ? AND greeting_sent = 0",
                (today,)
            )
            return [dict(row) for row in await cursor.fetchall()]
    
    async def mark_birthday_greeting_sent(self, birthday_id: int):
        """Отметить что поздравление отправлено"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE clients_birthdays SET greeting_sent = 1, updated_at = ? WHERE id = ?",
                (datetime.now(), birthday_id)
            )
            await self.conn.commit()


    # === ЦЕЛЕВЫЕ РЕСУРСЫ (TG чаты + VK группы) ===
    async def add_target_resource(self, resource_type: str, link: str, title: str = None) -> int:
        """Добавить ресурс для мониторинга"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO target_resources (type, link, title) VALUES (?, ?, ?)",
                (resource_type, link, title or link)
            )
            await self.conn.commit()
            return cursor.lastrowid
    
    async def get_target_resources(self, resource_type: str = None, active_only: bool = True) -> List[Dict]:
        """Получить список ресурсов"""
        async with self.conn.cursor() as cursor:
            if active_only:
                if resource_type:
                    await cursor.execute(
                        "SELECT * FROM target_resources WHERE type = ? AND is_active = 1",
                        (resource_type,)
                    )
                else:
                    await cursor.execute("SELECT * FROM target_resources WHERE is_active = 1")
            else:
                if resource_type:
                    await cursor.execute(
                        "SELECT * FROM target_resources WHERE type = ?",
                        (resource_type,)
                    )
                else:
                    await cursor.execute("SELECT * FROM target_resources")
            return [dict(row) for row in await cursor.fetchall()]
    
    async def remove_target_resource(self, resource_id: int):
        """Удалить ресурс"""
        async with self.conn.cursor() as cursor:
            await cursor.execute("DELETE FROM target_resources WHERE id = ?", (resource_id,))
            await self.conn.commit()
    
    async def toggle_resource_active(self, resource_id: int, is_active: bool):
        """Включить/выключить ресурс"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE target_resources SET is_active = ?, updated_at = ? WHERE id = ?",
                (is_active, datetime.now(), resource_id)
            )
            await self.conn.commit()
    
    async def update_last_post_id(self, resource_id: int, last_post_id: int):
        """Обновить ID последнего поста"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE target_resources SET last_post_id = ?, updated_at = ? WHERE id = ?",
                (last_post_id, datetime.now(), resource_id)
            )
            await self.conn.commit()
    
    # === КЛЮЧЕВЫЕ СЛОВА ===
    async def add_spy_keyword(self, keyword: str) -> int:
        """Добавить ключевое слово"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "INSERT OR IGNORE INTO spy_keywords (keyword) VALUES (?)",
                (keyword.lower(),)
            )
            await self.conn.commit()
            await cursor.execute("SELECT id FROM spy_keywords WHERE keyword = ?", (keyword.lower(),))
            row = await cursor.fetchone()
            return row['id'] if row else None
    
    async def remove_spy_keyword(self, keyword_id: int):
        """Удалить ключевое слово"""
        async with self.conn.cursor() as cursor:
            await cursor.execute("DELETE FROM spy_keywords WHERE id = ?", (keyword_id,))
            await self.conn.commit()
    
    async def get_spy_keywords(self, active_only: bool = True) -> List[Dict]:
        """Получить список ключевых слов"""
        async with self.conn.cursor() as cursor:
            if active_only:
                await cursor.execute("SELECT * FROM spy_keywords WHERE is_active = 1")
            else:
                await cursor.execute("SELECT * FROM spy_keywords")
            return [dict(row) for row in await cursor.fetchall()]
    
    async def toggle_keyword_active(self, keyword_id: int, is_active: bool):
        """Включить/выключить ключевое слово"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE spy_keywords SET is_active = ? WHERE id = ?",
                (is_active, keyword_id)
            )
            await self.conn.commit()


# === CONTENT HISTORY (Финансовый трекинг) ===
    async def add_content_history(
        self,
        post_text: str = None,
        image_url: str = None,
        model_used: str = None,
        cost_rub: float = None,
        platform: str = None,
        channel: str = None,
        post_id: int = None
    ) -> int:
        """Добавить запись в историю контента"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """INSERT INTO content_history 
                   (post_text, image_url, model_used, cost_rub, platform, channel, post_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (post_text, image_url, model_used, cost_rub, platform, channel, post_id)
            )
            await self.conn.commit()
            return cursor.lastrowid
    
    async def get_content_history(self, limit: int = 100) -> List[Dict]:
        """Получить историю контента"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT * FROM content_history ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in await cursor.fetchall()]
    
    async def get_financial_report(self, months: int = 6) -> Dict:
        """Получить финансовый отчет за N месяцев"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """SELECT 
                    model_used,
                    COUNT(*) as count,
                    SUM(cost_rub) as total_cost
                   FROM content_history 
                   WHERE created_at >= datetime('now', '-' || ? || ' months')
                   GROUP BY model_used""",
                (months,)
            )
            rows = await cursor.fetchall()
            return {row['model_used']: {'count': row['count'], 'total': row['total_cost']} for row in rows}
    
    async def cleanup_old_texts(self):
        """Удалить тексты старше 3 месяцев"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """UPDATE content_history 
                   SET post_text = NULL 
                   WHERE created_at < datetime('now', '-3 months') 
                   AND post_text IS NOT NULL"""
            )
            await self.conn.commit()
    
    async def cleanup_old_history(self):
        """Полная очистка записей старше 12 месяцев"""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """DELETE FROM content_history 
                   WHERE created_at < datetime('now', '-12 months')"""
            )
            await self.conn.commit()


db = Database()
