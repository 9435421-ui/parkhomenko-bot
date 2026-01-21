import sqlite3

def apply():
    conn = sqlite3.connect('parkhomenko_bot.db')
    cursor = conn.cursor()
    try:
        # Добавляем колонку image_prompt в таблицу content_plan
        cursor.execute("ALTER TABLE content_plan ADD COLUMN image_prompt TEXT")
        conn.commit()
        print("✅ Колонка image_prompt успешно добавлена в таблицу content_plan")
    except sqlite3.OperationalError:
        print("⚠️ Колонка image_prompt уже существует")
    finally:
        conn.close()

if __name__ == "__main__":
    apply()
