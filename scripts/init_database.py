#!/usr/bin/env python3
"""
Скрипт инициализации базы данных TERION.
Удаляет старую базу и создает новую с правильной структурой.
"""
import asyncio
import os
import sys

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def init_database():
    """Инициализация базы данных с правильной структурой"""
    from database.db import main_db
    
    # Подключаемся к БД
    await main_db.connect()
    
    try:
        # Создаем таблицу ресурсов с правильными колонками
        await main_db.execute('''
            CREATE TABLE IF NOT EXISTS target_resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link TEXT UNIQUE NOT NULL,
                type TEXT NOT NULL,
                title TEXT,
                is_active INTEGER DEFAULT 1,
                last_post_id INTEGER DEFAULT 0,
                last_lead_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Добавляем стартовые чаты ПИК и Самолет
        await main_db.execute(
            'INSERT OR IGNORE INTO target_resources (link, type, title, is_active) VALUES (?, ?, ?, ?)',
            ('pik_neighbors', 'telegram', 'ПИК Соседи', 1)
        )
        await main_db.execute(
            'INSERT OR IGNORE INTO target_resources (link, type, title, is_active) VALUES (?, ?, ?, ?)',
            ('samolet_live', 'telegram', 'Самолет Live', 1)
        )
        
        print('✅ База TERION инициализирована!')
        print('✅ Таблица target_resources создана')
        print('✅ Добавлены стартовые чаты: ПИК Соседи, Самолет Live')
        
    except Exception as e:
        print(f'❌ Ошибка инициализации базы: {e}')
        raise
    finally:
        if main_db.conn:
            await main_db.conn.close()

if __name__ == "__main__":
    asyncio.run(init_database())
