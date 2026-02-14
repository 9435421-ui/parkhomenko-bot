import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv('DATABASE_URL', 'sqlite:///parkhomenko_bot.db').replace('sqlite:///', '')

def migrate_content_plan():
    """Пересоздаёт таблицу content_plan с правильной структурой"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. Проверить, существует ли колонка type
        cursor.execute("PRAGMA table_info(content_plan)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'type' in columns:
            print("✅ Колонка 'type' уже существует, миграция не требуется")
            return

        print("⚠️  Колонка 'type' отсутствует, начинаем миграцию...")

        # 2. Сохранить старые данные (если есть)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='content_plan'")
        if cursor.fetchone():
            cursor.execute("CREATE TABLE content_plan_backup AS SELECT * FROM content_plan")
            print("📦 Создан бэкап старых данных")

        # 3. Удалить старую таблицу
        cursor.execute("DROP TABLE IF EXISTS content_plan")
        print("🗑️  Старая таблица удалена")

        # 4. Создать новую таблицу с правильной структурой
        cursor.execute("""
            CREATE TABLE content_plan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                title TEXT,
                body TEXT NOT NULL,
                cta TEXT,
                status TEXT DEFAULT 'draft',
                publish_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                image_prompt TEXT DEFAULT NULL,
                image_url TEXT DEFAULT NULL
            )
        """)
        print("✅ Новая таблица создана")

        # 5. Попытаться восстановить данные из бэкапа (если структура совместима)
        # Примечание: если старая структура сильно отличается, восстановление пропускаем

        conn.commit()
        print("✅ Миграция успешно завершена!")

    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_content_plan()
