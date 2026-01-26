import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL", "parkhomenko_bot.db")
        self.is_postgres = self.db_url.startswith("postgres://") or self.db_url.startswith("postgresql://")

    def _get_connection(self):
        """Создает и возвращает подключение к БД"""
        if self.is_postgres:
            conn = psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
            conn.autocommit = True
            return conn
        else:
            db_path = self.db_url.replace('sqlite:///', '')
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            return conn

    def connect(self):
        """Инициализация базы данных (создание таблиц)"""
        if self.is_postgres:
            logger.info("🔄 Initializing PostgreSQL database")
        else:
            logger.info(f"🔄 Initializing SQLite database: {self.db_url}")
        self._create_tables()

    def _create_tables(self):
        """Создание таблиц"""
        with self._get_connection() as conn:
            cur = conn.cursor()

            # Use SERIAL for Postgres, AUTOINCREMENT for SQLite
            id_type = "SERIAL PRIMARY KEY" if self.is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
            text_type = "TEXT"
            timestamp_default = "CURRENT_TIMESTAMP" if self.is_postgres else "(datetime('now'))"

            leads_sql = f"""
                CREATE TABLE IF NOT EXISTS leads (
                    id {id_type},
                    name {text_type},
                    phone {text_type},
                    extra_contact {text_type},
                    object_type {text_type},
                    city {text_type},
                    change_plan {text_type},
                    bti_status {text_type},
                    created_at TIMESTAMP DEFAULT {timestamp_default}
                )
            """
            content_sql = f"""
                CREATE TABLE IF NOT EXISTS content_plan (
                    id {id_type},
                    type {text_type} NOT NULL,
                    title {text_type},
                    body {text_type} NOT NULL,
                    cta {text_type} NOT NULL,
                    publish_date {text_type} NOT NULL,
                    status {text_type} DEFAULT 'draft',
                    image_prompt {text_type},
                    image_url {text_type},
                    created_at TIMESTAMP DEFAULT {timestamp_default},
                    published_at {text_type}
                )
            """
            subscribers_sql = f"""
                CREATE TABLE IF NOT EXISTS subscribers (
                    id {id_type},
                    user_id BIGINT UNIQUE NOT NULL,
                    username {text_type},
                    first_name {text_type},
                    last_name {text_type},
                    birthday {text_type},
                    added_at {text_type} NOT NULL,
                    notes {text_type}
                )
            """
            news_sql = f"""
                CREATE TABLE IF NOT EXISTS news (
                    id {id_type},
                    title {text_type} UNIQUE NOT NULL,
                    url {text_type},
                    summary {text_type},
                    published_at {text_type},
                    notified INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT {timestamp_default}
                )
            """

            cur.execute(leads_sql)
            cur.execute(content_sql)
            cur.execute(subscribers_sql)
            cur.execute(news_sql)

            if not self.is_postgres:
                conn.commit()

    def save_lead(self, name, phone, extra_contact=None, object_type=None,
                       city=None, change_plan=None, bti_status=None):
        query = """
            INSERT INTO leads (name, phone, extra_contact, object_type, city, change_plan, bti_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """ if self.is_postgres else """
            INSERT INTO leads (name, phone, extra_contact, object_type, city, change_plan, bti_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, (name, phone, extra_contact, object_type,
                                city, change_plan, bti_status))
            if not self.is_postgres: conn.commit()

    def save_post(self, post_type, title, body, cta, publish_date, image_prompt=None, image_url=None):
        placeholder = "%s" if self.is_postgres else "?"
        query = f"""
            INSERT INTO content_plan (type, title, body, cta, publish_date, status, image_prompt, image_url)
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, 'draft', {placeholder}, {placeholder})
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, (post_type, title, body, cta, publish_date.isoformat(), image_prompt, image_url))
            if self.is_postgres:
                # In postgres RealDictCursor doesn't have lastrowid easily
                cur.execute("SELECT LASTVAL()")
                last_id = cur.fetchone()['lastval']
            else:
                conn.commit()
                last_id = cur.lastrowid
            return last_id

    def get_draft_posts(self):
        query = "SELECT * FROM content_plan WHERE status='draft' ORDER BY created_at DESC"
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query)
            rows = cur.fetchall()
            return [dict(row) for row in rows]

    def update_content_plan_entry(self, post_id: int, status: str = None, publish_date: str = None, image_prompt: str = None, image_url: str = None):
        updates = []
        params = []
        placeholder = "%s" if self.is_postgres else "?"

        if status:
            updates.append(f"status = {placeholder}")
            params.append(status)
        if publish_date:
            updates.append(f"publish_date = {placeholder}")
            params.append(publish_date)
        if image_prompt is not None:
            updates.append(f"image_prompt = {placeholder}")
            params.append(image_prompt)
        if image_url is not None:
            updates.append(f"image_url = {placeholder}")
            params.append(image_url)

        if not updates: return
        params.append(post_id)

        query = f"UPDATE content_plan SET {', '.join(updates)} WHERE id = {placeholder}"
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            if not self.is_postgres: conn.commit()

    def get_max_publish_date(self, status='approved'):
        placeholder = "%s" if self.is_postgres else "?"
        query = f"SELECT MAX(publish_date) FROM content_plan WHERE status = {placeholder}"
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, (status,))
            row = cur.fetchone()
            val = row['max'] if self.is_postgres else row[0]
            if val:
                try:
                    return datetime.strptime(val, '%Y-%m-%d %H:%M:%S')
                except:
                    return datetime.fromisoformat(val)
            return None

    def delete_post(self, post_id):
        placeholder = "%s" if self.is_postgres else "?"
        query = f"DELETE FROM content_plan WHERE id={placeholder}"
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, (post_id,))
            if not self.is_postgres: conn.commit()

    def get_posts_to_publish(self):
        now_func = "NOW()" if self.is_postgres else "datetime('now')"
        query = f"""
            SELECT * FROM content_plan
            WHERE status='approved' AND publish_date <= {now_func}
            ORDER BY publish_date
        """
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query)
            return [dict(row) for row in cur.fetchall()]

    def mark_as_published(self, post_id):
        placeholder = "%s" if self.is_postgres else "?"
        now_func = "NOW()" if self.is_postgres else "datetime('now')"
        query = f"UPDATE content_plan SET status='published', published_at={now_func} WHERE id={placeholder}"
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, (post_id,))
            if not self.is_postgres: conn.commit()

    def get_all_posts(self, limit=50):
        query = f"SELECT * FROM content_plan ORDER BY created_at DESC LIMIT {limit}"
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query)
            return [dict(row) for row in cur.fetchall()]

    def add_subscriber(self, user_id, username=None, first_name=None, last_name=None, birthday=None, notes=None):
        if self.is_postgres:
            query = """
                INSERT INTO subscribers (user_id, username, first_name, last_name, birthday, added_at, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                username=EXCLUDED.username, first_name=EXCLUDED.first_name, last_name=EXCLUDED.last_name,
                birthday=EXCLUDED.birthday, notes=EXCLUDED.notes
            """
        else:
            query = """
                INSERT OR REPLACE INTO subscribers (user_id, username, first_name, last_name, birthday, added_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, (user_id, username, first_name, last_name, birthday, datetime.now().isoformat(), notes))
            if not self.is_postgres: conn.commit()

    def get_subscriber(self, user_id):
        placeholder = "%s" if self.is_postgres else "?"
        query = f"SELECT * FROM subscribers WHERE user_id={placeholder}"
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_all_subscribers(self):
        query = "SELECT * FROM subscribers ORDER BY added_at DESC"
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query)
            return [dict(row) for row in cur.fetchall()]

    def get_today_birthdays(self):
        today = datetime.now().strftime("%d.%m")
        placeholder = "%s" if self.is_postgres else "?"
        query = f"SELECT * FROM subscribers WHERE birthday LIKE {placeholder} OR birthday LIKE {placeholder}"
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, (f"{today}.%", f"{today}"))
            return [dict(row) for row in cur.fetchall()]

    def add_news(self, title, url=None, summary=None, published_at=None):
        if self.is_postgres:
            query = "INSERT INTO news (title, url, summary, published_at) VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING"
        else:
            query = "INSERT OR IGNORE INTO news (title, url, summary, published_at) VALUES (?, ?, ?, ?)"
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, (title, url, summary, published_at))
            if not self.is_postgres: conn.commit()

    def get_unnotified_news(self):
        query = "SELECT * FROM news WHERE notified = 0 ORDER BY created_at ASC"
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query)
            return [dict(row) for row in cur.fetchall()]

    def mark_news_as_notified(self, news_id):
        placeholder = "%s" if self.is_postgres else "?"
        query = f"UPDATE news SET notified = 1 WHERE id = {placeholder}"
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, (news_id,))
            if not self.is_postgres: conn.commit()










    def get_upcoming_birthdays(self, days=7):
        subscribers = self.get_all_subscribers()
        import datetime
        from datetime import datetime as dt
        upcoming = []
        today = dt.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for s in subscribers:
            if not s["birthday"]: continue
            try:
                parts = s["birthday"].split(".")
                day = int(parts[0])
                month = int(parts[1])
                bday = today.replace(month=month, day=day)
                if bday < today: bday = bday.replace(year=today.year + 1)
                diff = (bday - today).days
                if 0 <= diff <= days:
                    s["days_until_birthday"] = diff
                    upcoming.append(s)
            except: continue
        return sorted(upcoming, key=lambda x: x["days_until_birthday"])

db = Database()
if __name__ == "__main__":
    db.connect()
    print("✅ Database initialized successfully.")
