import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv('DATABASE_PATH', 'database/bot.db')

def apply_migration():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(leads)")
        columns = [row[1] for row in cursor.fetchall()]

        new_columns = [
            ('qualification_started', 'BOOLEAN DEFAULT 0'),
            ('night_lead', 'BOOLEAN DEFAULT 0')
        ]

        for col_name, col_type in new_columns:
            if col_name not in columns:
                cursor.execute(f"ALTER TABLE leads ADD COLUMN {col_name} {col_type}")
                print(f"✅ Колонка {col_name} добавлена в modular leads")
            else:
                print(f"⚠️  Колонка {col_name} уже существует в modular leads")

        conn.commit()
        print("✅ Миграция modular_db успешно применена")

    except Exception as e:
        print(f"❌ Ошибка миграции modular_db: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    apply_migration()
