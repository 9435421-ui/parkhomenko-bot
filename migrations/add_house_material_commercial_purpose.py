import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv('DATABASE_URL', 'sqlite:///parkhomenko_bot.db').replace('sqlite:///', '')

def migrate():
    """Добавить колонки house_material и commercial_purpose в leads"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Проверить, существуют ли колонки
        cursor.execute("PRAGMA table_info(leads)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'house_material' in columns and 'commercial_purpose' in columns:
            print("✅ Колонки house_material и commercial_purpose уже существуют")
            return

        if 'house_material' not in columns:
            cursor.execute("""
                ALTER TABLE leads
                ADD COLUMN house_material TEXT
            """)
            print("✅ Колонка house_material добавлена")

        if 'commercial_purpose' not in columns:
            cursor.execute("""
                ALTER TABLE leads
                ADD COLUMN commercial_purpose TEXT
            """)
            print("✅ Колонка commercial_purpose добавлена")

        conn.commit()
        print("✅ Миграция успешно применена")

    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
