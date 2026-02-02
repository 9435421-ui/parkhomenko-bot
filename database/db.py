import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect("parkhomenko_bot.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS unified_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER,
            username TEXT,
            full_name TEXT,
            phone TEXT,
            property_type TEXT,
            stage TEXT,
            area TEXT,
            source TEXT,
            bot_label TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    print("Таблица unified_leads создана/обновлена")
