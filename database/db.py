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
                    pain_stage TEXT,
                    priority_score INTEGER,
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
            # Миграция: колонка notes в target_resources («Обнаружен автоматически» и т.д.)
            try:
                await cursor.execute("ALTER TABLE target_resources ADD COLUMN notes TEXT NULL")
                await self.conn.commit()
            except Exception:
                pass
            # Миграция: колонка last_post_id в target_resources
            try:
                await cursor.execute("ALTER TABLE target_resources ADD COLUMN last_post_id INTEGER DEFAULT 0")
                await self.conn.commit()
            except Exception:
                pass
            # Миграция spy_leads: pain_stage, priority_score
            for col, ctype in [("pain_stage", "TEXT"), ("priority_score", "INTEGER")]:
                try:
                    await cursor.execute(f"ALTER TABLE spy_leads ADD COLUMN {col} {ctype}")
                    await self.conn.commit()
                except Exception:
                    pass
            # Data-Driven Scout: status (pending/active/archived), platform, geo_tag, participants_count
            try:
                await cursor.execute("ALTER TABLE target_resources ADD COLUMN status TEXT DEFAULT 'pending'")
                await self.conn.commit()
            except Exception:
                pass
            try:
                await cursor.execute("ALTER TABLE target_resources ADD COLUMN platform TEXT NULL")
                await self.conn.commit()
            except Exception:
                pass
            try:
                await cursor.execute("ALTER TABLE target_resources ADD COLUMN geo_tag TEXT NULL")
                await self.conn.commit()
            except Exception:
                pass
            try:
                await cursor.execute("ALTER TABLE target_resources ADD COLUMN participants_count INTEGER NULL")
                await self.conn.commit()
            except Exception:
                pass
            # Привести старые записи: status='active' где is_active=1
            try:
                await cursor.execute("UPDATE target_resources SET status = 'active' WHERE is_active = 1 AND (status IS NULL OR status = '')")
                await cursor.execute("UPDATE target_resources SET status = 'archived' WHERE (is_active = 0 OR is_active IS NULL) AND (status IS NULL OR status = '')")
                await cursor.execute("UPDATE target_resources SET platform = type WHERE platform IS NULL OR platform = ''")
                await self.conn.commit()
            except Exception:
                pass
            # Снайпер v3.0: приоритетные ЖК (высотки)
            try:
                await cursor.execute("ALTER TABLE target_resources ADD COLUMN is_high_priority INTEGER DEFAULT 0")
                await self.conn.commit()
            except Exception:
                pass
            # Модуль «Ассистент Продаж»: скрипты подсказок для карточки лида
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS sales_templates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    key TEXT NOT NULL UNIQUE,
                    body TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await self.conn.commit()
            for key, body in [
                ("mji_prescription", "Срочный выезд и аудит документов"),
                ("keys_design", "Проверка проекта на реализуемость"),
            ]:
                await cursor.execute(
                    "INSERT OR IGNORE INTO sales_templates (key, body) VALUES (?, ?)",
                    (key, body),
                )
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
        pain_stage: Optional[str] = None,
        priority_score: Optional[int] = None,
    ) -> int:
        """Сохранить лид от шпиона: источник, автор, ссылка на профиль, текст, стадия боли, оценка приоритета."""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """INSERT INTO spy_leads (source_type, source_name, author_id, username, profile_url, text, url, pain_stage, priority_score)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (source_type, source_name, author_id or None, username or None, profile_url or None, text or "", url, pain_stage, priority_score),
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
                """SELECT * FROM spy_leads WHERE created_at >= datetime('now', ?)
                   ORDER BY created_at DESC""",
                (f"-{since_hours} hours",),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_latest_spy_leads(self, limit: int = 5) -> List[Dict]:
        """Получить последние найденные лиды."""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT * FROM spy_leads ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_spy_lead(self, lead_id: int) -> Optional[Dict]:
        """Получить лид из spy_leads по id (для кнопки «Ответить от имени Антона»)."""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT id, source_type, source_name, author_id, username, profile_url, text, url FROM spy_leads WHERE id = ?",
                (lead_id,),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

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

    async def get_top_trends(self, since_days: int = 7, limit: int = 15) -> List[Dict]:
        """
        Аналитика для креативщика: группировка лидов по темам (доля в %).
        Темы заданы ключевыми фразами; считается, сколько лидов содержат каждую тему.
        """
        topic_keywords = [
            ("ипотека", "ипотек"),
            ("перепланировк", "перепланировку", "согласован"),
            ("Москва-Сити", "Сити", "в Сити"),
            ("узаконить", "узакони"),
            ("лоджи", "лоджию", "балкон"),
            ("нежилое", "нежилое помещение", "коммерц"),
            ("МЖИ", "Мосжилинспекц", "жилинспекц"),
            ("штраф", "штрафы"),
            ("проект", "проект перепланировки"),
            ("ремонт", "ремонт"),
        ]
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """SELECT id, text FROM spy_leads
                   WHERE created_at >= datetime('now', ?)
                   AND text IS NOT NULL AND text != ''""",
                (f"-{since_days} days",),
            )
            rows = await cursor.fetchall()
        leads = [dict(r) for r in rows]
        total = len(leads)
        if total == 0:
            return []
        counts = {}
        for topic_name, *keywords in topic_keywords:
            key = topic_name if isinstance(topic_name, str) else keywords[0]
            count = 0
            for lead in leads:
                text = (lead.get("text") or "").lower()
                if any(kw.lower() in text for kw in (topic_name, *keywords)):
                    count += 1
            if count > 0:
                counts[key] = count
        total_matched = sum(counts.values())
        if total_matched == 0:
            return []
        result = [
            {"topic": topic, "count": count, "percent": round(100.0 * count / total, 1)}
            for topic, count in sorted(counts.items(), key=lambda x: -x[1])
        ]
        return result[:limit]

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

    async def get_sales_template(self, key: str) -> Optional[str]:
        """Получить скрипт подсказки по ключу (модуль Ассистент Продаж)."""
        async with self.conn.cursor() as cursor:
            try:
                await cursor.execute("SELECT body FROM sales_templates WHERE key = ?", (key,))
                row = await cursor.fetchone()
                return row[0] if row else None
            except Exception:
                return None

    async def set_sales_template(self, key: str, body: str) -> None:
        """Обновить скрипт подсказки."""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "INSERT OR REPLACE INTO sales_templates (key, body, updated_at) VALUES (?, ?, ?)",
                (key, body, datetime.now()),
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


    # === ЦЕЛЕВЫЕ РЕСУРСЫ (Data-Driven Scout) ===
    async def add_target_resource(
        self,
        resource_type: str,
        link: str,
        title: str = None,
        notes: str = None,
        status: str = "pending",
        participants_count: int = None,
        geo_tag: str = None,
    ) -> int:
        """Добавить ресурс. status: pending|active|archived. При дубликате link — обновить participants_count и notes."""
        link = (link or "").strip().rstrip("/")
        title = title or link
        platform = resource_type  # telegram | vk
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """SELECT id FROM target_resources WHERE REPLACE(REPLACE(link, 'https://', ''), 'http://', '') = REPLACE(REPLACE(?, 'https://', ''), 'http://', '') OR link = ? OR link = ?""",
                (link, link, link + "/"),
            )
            row = await cursor.fetchone()
            if row:
                rid = row[0]
                await cursor.execute(
                    "UPDATE target_resources SET title = ?, notes = COALESCE(?, notes), participants_count = COALESCE(?, participants_count), platform = ?, updated_at = ? WHERE id = ?",
                    (title, notes, participants_count, platform, datetime.now(), rid),
                )
                await self.conn.commit()
                return rid
            try:
                await cursor.execute(
                    """INSERT INTO target_resources (type, link, title, notes, status, participants_count, geo_tag, platform) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (resource_type, link, title, notes, status, participants_count, geo_tag, platform),
                )
            except Exception:
                await cursor.execute(
                    "INSERT INTO target_resources (type, link, title, notes) VALUES (?, ?, ?, ?)",
                    (resource_type, link, title, notes),
                )
            await self.conn.commit()
            return cursor.lastrowid

    async def get_target_resource_by_link(self, link: str) -> Optional[Dict]:
        """Проверить, есть ли ресурс с такой ссылкой (для режима «Разведка» и ловли ссылок)."""
        if not link or not link.strip():
            return None
        link_clean = link.strip().rstrip("/")
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT * FROM target_resources WHERE link = ? OR link = ?",
                (link_clean, link_clean + "/"),
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_active_targets_for_scout(self, platform: Optional[str] = None) -> List[Dict]:
        """Список целей для парсера/хантера. Поля: link, title, geo_tag, id, is_high_priority, last_lead_at, last_post_id."""
        async with self.conn.cursor() as cursor:
            query = """SELECT id, link, title, COALESCE(geo_tag, '') AS geo_tag,
                          COALESCE(is_high_priority, 0) AS is_high_priority, last_lead_at, last_post_id,
                          COALESCE(platform, type) as platform
                       FROM target_resources
                       WHERE (status = 'active' OR (is_active = 1 AND (status IS NULL OR status = '')))"""
            params = []
            if platform:
                query += " AND (platform = ? OR type = ?)"
                params.extend([platform, platform])

            try:
                await cursor.execute(query, params)
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
            except Exception as e:
                logger.error(f"Ошибка получения целей для скаута: {e}")
                return []

    async def update_target_last_lead_at(self, link: str) -> None:
        """Обновить время последнего найденного лида по ресурсу (для исключения из скана через 48ч)."""
        link_clean = (link or "").strip().rstrip("/")
        if not link_clean:
            return
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE target_resources SET last_lead_at = ?, updated_at = ? WHERE link = ? OR link = ?",
                (datetime.now(), datetime.now(), link_clean, link_clean + "/"),
            )
            await self.conn.commit()

    async def get_pending_targets(self) -> List[Dict]:
        """Список ресурсов со статусом pending для /approve_targets. Поля: id, title, link, participants_count."""
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                """SELECT id, link, title, participants_count FROM target_resources
                   WHERE status = 'pending'
                   ORDER BY COALESCE(participants_count, 0) DESC, id"""
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def set_target_status(self, resource_id: int, status: str):
        """Установить статус: active | archived | pending. Синхронизирует is_active с status."""
        is_active = 1 if status == "active" else 0
        async with self.conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE target_resources SET status = ?, is_active = ?, updated_at = ? WHERE id = ?",
                (status, is_active, datetime.now(), resource_id),
            )
            await self.conn.commit()

    async def set_target_geo(self, resource_id: int = None, link: str = None, geo_tag: str = "") -> bool:
        """Установить geo_tag для ресурса по id или по link. Возвращает True если обновлено."""
        if not geo_tag and resource_id is None and not link:
            return False
        async with self.conn.cursor() as cursor:
            if resource_id is not None:
                await cursor.execute(
                    "UPDATE target_resources SET geo_tag = ?, updated_at = ? WHERE id = ?",
                    (geo_tag.strip(), datetime.now(), resource_id),
                )
            elif link:
                link_clean = (link or "").strip().rstrip("/")
                await cursor.execute(
                    "UPDATE target_resources SET geo_tag = ?, updated_at = ? WHERE link = ? OR link = ?",
                    (geo_tag.strip(), datetime.now(), link_clean, link_clean + "/"),
                )
            else:
                return False
            await self.conn.commit()
            return cursor.rowcount > 0

    async def set_target_high_priority(self, resource_id: int = None, link: str = None, is_high: bool = True) -> bool:
        """Пометить ресурс как приоритетный ЖК (высотка). По id или по link."""
        async with self.conn.cursor() as cursor:
            val = 1 if is_high else 0
            if resource_id is not None:
                await cursor.execute(
                    "UPDATE target_resources SET is_high_priority = ?, updated_at = ? WHERE id = ?",
                    (val, datetime.now(), resource_id),
                )
            elif link:
                link_clean = (link or "").strip().rstrip("/")
                await cursor.execute(
                    "UPDATE target_resources SET is_high_priority = ?, updated_at = ? WHERE link = ? OR link = ?",
                    (val, datetime.now(), link_clean, link_clean + "/"),
                )
            else:
                return False
            await self.conn.commit()
            return cursor.rowcount > 0

    async def import_scan_to_target_resources(
        self, chats: List[Dict], min_participants: int = 500
    ) -> int:
        """
        Импорт результата scan_all_chats: чаты с participants_count > min_participants
        добавляются в target_resources со статусом pending (без дубликатов по link).
        Возвращает количество добавленных/обновлённых записей.
        """
        count = 0
        for ch in chats:
            link = (ch.get("link") or "").strip().rstrip("/")
            if not link:
                continue
            participants = ch.get("participants_count")
            if participants is not None and participants < min_participants:
                continue
            title = ch.get("title") or link
            existing = await self.get_target_resource_by_link(link)
            if existing:
                if participants is not None and existing.get("participants_count") != participants:
                    async with self.conn.cursor() as cursor:
                        await cursor.execute(
                            "UPDATE target_resources SET participants_count = ?, updated_at = ? WHERE id = ?",
                            (participants, datetime.now(), existing["id"]),
                        )
                        await self.conn.commit()
                continue
            await self.add_target_resource(
                "telegram", link, title=title, notes="Импорт из /scan_chats", status="pending", participants_count=participants
            )
            count += 1
        return count

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

    async def reset_all_last_post_ids(self):
        """Сбросить все last_post_id для повторного сканирования всех сообщений."""
        async with self.conn.cursor() as cursor:
            await cursor.execute("UPDATE target_resources SET last_post_id = 0")
            await self.conn.commit()
            logger.info("🔄 Все last_post_id в target_resources сброшены в 0.")
    
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