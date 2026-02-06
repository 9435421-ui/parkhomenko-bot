import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv('DATABASE_URL', 'sqlite:///parkhomenko_bot.db').replace('sqlite:///', '')

def apply_migration():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Проверяем, существуют ли уже колонки
        cursor.execute("PRAGMA table_info(content_plan)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'image_prompt' not in columns:
            cursor.execute("ALTER TABLE content_plan ADD COLUMN image_prompt TEXT DEFAULT NULL")
            print("✅ Колонка image_prompt добавлена")
        else:
            print("⚠️  Колонка image_prompt уже существует")

        if 'image_url' not in columns:
            cursor.execute("ALTER TABLE content_plan ADD COLUMN image_url TEXT DEFAULT NULL")
            print("✅ Колонка image_url добавлена")
        else:
            print("⚠️  Колонка image_url уже существует")

        conn.commit()
        print("✅ Миграция успешно применена")

    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    apply_migration()
