#!/usr/bin/env python3
"""
Одноразовый скрипт для добавления колонки updated_at в таблицу sources
"""
import sqlite3
import os
from pathlib import Path

def get_db_path():
    """Определяет путь к базе данных по той же логике, что и Database.__init__"""
    # Проверяем переменную окружения DATABASE_PATH
    env_db_path = os.getenv("DATABASE_PATH")
    if env_db_path:
        return str(Path(env_db_path).resolve())
    
    # Дефолт: parkhomenko_bot.db
    db_path = Path("parkhomenko_bot.db")
    return str(db_path.resolve())

def fix_sources_table():
    """Проверяет и добавляет колонку updated_at в таблицу sources"""
    db_path = get_db_path()
    
    print(f"📂 Подключение к базе данных: {db_path}")
    
    if not Path(db_path).exists():
        print(f"❌ Ошибка: файл базы данных не найден: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем структуру таблицы sources
        cursor.execute("PRAGMA table_info(sources)")
        columns = cursor.fetchall()
        column_names = [col_info[1] for col_info in columns]
        
        print(f"📋 Найдено колонок в таблице sources: {len(column_names)}")
        print(f"   Колонки: {', '.join(column_names)}")
        
        if 'updated_at' in column_names:
            print("✅ Колонка updated_at уже существует в таблице sources")
            conn.close()
            return True
        
        # Добавляем колонку updated_at
        print("🔧 Добавляю колонку updated_at в таблицу sources...")
        cursor.execute("ALTER TABLE sources ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        
        # Обновляем существующие записи (если есть)
        cursor.execute("UPDATE sources SET updated_at = COALESCE(last_scanned, CURRENT_TIMESTAMP) WHERE updated_at IS NULL")
        
        conn.commit()
        conn.close()
        
        print("✅ Колонка updated_at успешно добавлена в таблицу sources")
        return True
        
    except sqlite3.OperationalError as e:
        if "no such table: sources" in str(e):
            print("⚠️  Таблица sources не существует. Она будет создана при следующем запуске бота.")
            return True
        else:
            print(f"❌ Ошибка SQLite: {e}")
            return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 Скрипт исправления базы данных")
    print("=" * 60)
    
    success = fix_sources_table()
    
    print("=" * 60)
    if success:
        print("✅ Исправление завершено успешно!")
    else:
        print("❌ Исправление завершилось с ошибками")
    print("=" * 60)
