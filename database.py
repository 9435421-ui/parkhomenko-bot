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
                    qualification_started BOOLEAN DEFAULT 0,
                    night_lead BOOLEAN DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """
            content_sql = """
                CREATE TABLE IF NOT EXISTS content_plan (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    title TEXT,
                    body TEXT NOT NULL,
                    cta TEXT NOT NULL,
                    publish_date TEXT NOT NULL,
                    status TEXT DEFAULT 'draft',
                    created_at TEXT DEFAULT (datetime('now')),
                    published_at TEXT
                )
            """
            subscribers_sql = """
                CREATE TABLE IF NOT EXISTS subscribers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    birthday TEXT,  -- format: DD.MM or DD.MM.YYYY
                    added_at TEXT NOT NULL,
                    notes TEXT
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
                    type VARCHAR(20) NOT NULL,
                    title TEXT,
                    body TEXT NOT NULL,
                    cta TEXT NOT NULL,
                    publish_date TIMESTAMP NOT NULL,
                    status VARCHAR(20) DEFAULT 'draft',
                    created_at TIMESTAMP DEFAULT NOW(),
                    published_at TIMESTAMP
                )
            """
            subscribers_sql = """
                CREATE TABLE IF NOT EXISTS subscribers (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    birthday TEXT,  -- format: DD.MM or DD.MM.YYYY
                    added_at TIMESTAMP NOT NULL,
                    notes TEXT
                )
            """

        async with self.conn.cursor() as cur:
            await cur.execute(leads_sql)
            await cur.execute(content_sql)
            await cur.execute(subscribers_sql)
        await self.conn.commit()

    # Функции для работы с лидами
    async def save_lead(self, user_id: int, **kwargs):
        """
        Сохранить или обновить лид.
        Если для этого user_id есть лид, созданный менее 24 часов назад, обновляем его.
        """
        # Проверяем наличие недавнего лида
        query_check = """
            SELECT id FROM leads
            WHERE user_id = ? AND created_at > datetime('now', '-1 day')
            ORDER BY created_at DESC LIMIT 1
        """
        async with self.conn.cursor() as cur:
            await cur.execute(query_check, (user_id,))
            row = await cur.fetchone()

            if row:
                # Обновление существующего лида
                lead_id = row[0]
                if not kwargs:
                    return lead_id

                set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
                values = list(kwargs.values()) + [lead_id]
                query_update = f"UPDATE leads SET {set_clause} WHERE id = ?"
                await cur.execute(query_update, values)
                await self.conn.commit()
                return lead_id
            else:
                # Создание нового лида
                kwargs['user_id'] = user_id
                columns = ", ".join(kwargs.keys())
                placeholders = ", ".join(["?" for _ in kwargs])
                query_insert = f"INSERT INTO leads ({columns}) VALUES ({placeholders})"
                await cur.execute(query_insert, list(kwargs.values()))
                await self.conn.commit()
                return cur.lastrowid

    # Функции для работы с контент-планом
    async def save_post(self, post_type, title, body, cta, publish_date, image_prompt=None, image_url=None):
        """Сохранить пост в контент-план"""
        query = """
            INSERT INTO content_plan (type, title, body, cta, publish_date, status, image_prompt, image_url)
            VALUES (?, ?, ?, ?, ?, 'draft', ?, ?)
        """
        async with self.conn.cursor() as cur:
            await cur.execute(query, (post_type, title, body, cta, publish_date.isoformat(), image_prompt, image_url))
            return cur.lastrowid
        await self.conn.commit()

    async def get_draft_posts(self):
        """Получить все посты со статусом draft"""
        query = """
            SELECT id, type, title, body, cta, publish_date, status, created_at, image_prompt, image_url
            FROM content_plan
            WHERE status='draft'
            ORDER BY created_at DESC
        """
        async with self.conn.cursor() as cur:
            await cur.execute(query)
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

    async def approve_post(self, post_id):
        """Утвердить пост"""
        query = "UPDATE content_plan SET status='approved' WHERE id=?"
        async with self.conn.cursor() as cur:
            await cur.execute(query, (post_id,))
        await self.conn.commit()

    async def update_content_plan_entry(self, post_id: int, status: str = None, publish_date: str = None, image_prompt: str = None, image_url: str = None):
        """Обновить запись в контент-плане"""
        updates = []
        params = []

        if status:
            updates.append("status = ?")
            params.append(status)
        if publish_date:
            updates.append("publish_date = ?")
            params.append(publish_date)
        if image_prompt is not None:
            updates.append("image_prompt = ?")
            params.append(image_prompt)
        if image_url is not None:
            updates.append("image_url = ?")
            params.append(image_url)

        if not updates:
            return  # Nothing to update

        params.append(post_id)

        query = f"UPDATE content_plan SET {', '.join(updates)} WHERE id = ?"
        async with self.conn.cursor() as cur:
            await cur.execute(query, params)
        await self.conn.commit()

    async def get_max_publish_date(self, status='approved'):
        """Возвращает максимальную publish_date среди постов с указанным статусом"""
        from datetime import datetime

        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT MAX(publish_date) FROM content_plan WHERE status = ?",
                (status,)
            )
            result = await cur.fetchone()

            if result and result[0]:
                return datetime.strptime(result[0], '%Y-%m-%d %H:%M:%S')
            return None

    async def delete_post(self, post_id):
        """Удалить пост"""
        query = "DELETE FROM content_plan WHERE id=?"
        async with self.conn.cursor() as cur:
            await cur.execute(query, (post_id,))
        await self.conn.commit()

    async def get_posts_to_publish(self):
        """Получить посты, готовые к публикации"""
        query = """
            SELECT id, type, title, body, cta, publish_date, image_prompt, image_url
            FROM content_plan
            WHERE status='approved' AND publish_date <= datetime('now')
            ORDER BY publish_date
        """
        async with self.conn.cursor() as cur:
            await cur.execute(query)
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

    async def mark_as_published(self, post_id):
        """Отметить пост как опубликованный"""
        query = "UPDATE content_plan SET status='published', published_at=datetime('now') WHERE id=?"
        async with self.conn.cursor() as cur:
            await cur.execute(query, (post_id,))
        await self.conn.commit()

    async def get_all_posts(self, limit=50):
        """Получить все посты для просмотра"""
        query = f"""
            SELECT id, type, title, body, cta, publish_date, status, created_at, published_at, image_prompt, image_url
            FROM content_plan
            ORDER BY created_at DESC
            LIMIT {limit}
        """
        async with self.conn.cursor() as cur:
            await cur.execute(query)
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

    # Функции для работы с подписчиками (дни рождения и праздники)
    async def add_subscriber(self, user_id, username=None, first_name=None, last_name=None,
                           birthday=None, notes=None):
        """Добавить подписчика"""
        query = """
            INSERT OR REPLACE INTO subscribers (user_id, username, first_name, last_name, birthday, added_at, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        async with self.conn.cursor() as cur:
            await cur.execute(query, (user_id, username, first_name, last_name,
                                    birthday, datetime.now().isoformat(), notes))
        await self.conn.commit()

    async def delete_subscriber(self, user_id):
        """Удалить подписчика"""
        query = "DELETE FROM subscribers WHERE user_id=?"
        async with self.conn.cursor() as cur:
            await cur.execute(query, (user_id,))
        await self.conn.commit()

    async def get_subscriber(self, user_id):
        """Получить подписчика по user_id"""
        query = "SELECT * FROM subscribers WHERE user_id=?"
        async with self.conn.cursor() as cur:
            await cur.execute(query, (user_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_all_subscribers(self):
        """Получить всех подписчиков"""
        query = "SELECT * FROM subscribers ORDER BY added_at DESC"
        async with self.conn.cursor() as cur:
            await cur.execute(query)
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

    async def get_today_birthdays(self):
        """Получить подписчиков с днем рождения сегодня"""
        today = datetime.now().strftime("%d.%m")
        query = """
            SELECT * FROM subscribers
            WHERE birthday LIKE ? OR birthday LIKE ?
        """
        async with self.conn.cursor() as cur:
            await cur.execute(query, (f"{today}.%", f"{today}"))
            rows = await cur.fetchall()
            return [dict(row) for row in rows]

    async def get_upcoming_birthdays(self, days_ahead=7):
        """Получить подписчиков с днями рождения в ближайшие N дней"""
        from datetime import timedelta

        # Получить всех подписчиков с днями рождения
        all_subscribers = await self.get_all_subscribers()
        upcoming = []
        today = datetime.now().date()

        for subscriber in all_subscribers:
            if not subscriber.get('birthday'):
                continue

            try:
                # Парсим день рождения (DD.MM или DD.MM.YYYY)
                birthday_str = subscriber['birthday']
                if '.' in birthday_str:
                    parts = birthday_str.split('.')
                    day = int(parts[0])
                    month = int(parts[1])

                    # Определяем год (текущий или следующий)
                    current_year = today.year
                    birthday_this_year = datetime(current_year, month, day).date()

                    if birthday_this_year < today:
                        # День рождения уже прошел в этом году, берем следующий год
                        birthday_this_year = datetime(current_year + 1, month, day).date()

                    # Проверяем, попадает ли в диапазон
                    days_until_birthday = (birthday_this_year - today).days
                    if 0 <= days_until_birthday <= days_ahead:
                        subscriber_copy = subscriber.copy()
                        subscriber_copy['days_until_birthday'] = days_until_birthday
                        upcoming.append(subscriber_copy)

            except (ValueError, IndexError):
                # Пропускаем некорректные даты
                continue

        return upcoming

    async def update_subscriber_birthday(self, user_id, birthday):
        """Обновить день рождения подписчика"""
        query = "UPDATE subscribers SET birthday=? WHERE user_id=?"
        async with self.conn.cursor() as cur:
            await cur.execute(query, (birthday, user_id))
        await self.conn.commit()

# Глобальный экземпляр базы данных
db = Database()
