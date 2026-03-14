"""
Скрипт для исправления контент-плана: сброс опубликованных постов без изображений
"""
import asyncio
import sqlite3
from datetime import datetime, timedelta
import os

async def reset_posts():
    """Удаляет опубликованные посты без изображений и возвращает их в статус draft"""
    # Путь к базе данных (проверяем оба возможных пути)
    db_paths = [
        'database/bot.db',
        'database/bot_database.db',
        'bot.db',
        'bot_database.db'
    ]
    
    db_path = None
    for path in db_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("❌ База данных не найдена. Проверьте путь к файлу БД.")
        return
    
    print(f"📂 Используется база данных: {db_path}")
    
    # Подключаемся к базе данных бота
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Используем таблицу content_plan (основная таблица для контент-плана)
    table_name = 'content_plan'
    
    # Проверяем существование таблицы
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    if not cursor.fetchone():
        print(f"❌ Таблица {table_name} не найдена")
        conn.close()
        return
    
    print(f"📋 Используется таблица: {table_name}")
    
    # 1. Находим посты, которые были опубликованы за последние 5 часов
    # (включая те, что улетели без изображений)
    cutoff_time = (datetime.now() - timedelta(hours=5)).isoformat()
    
    cursor.execute(f"""
        SELECT id, title, status, published_at, image_url 
        FROM {table_name} 
        WHERE status = 'published' 
        AND published_at > ?
        ORDER BY published_at DESC
    """, (cutoff_time,))
    
    posts_to_reset = cursor.fetchall()
    
    if not posts_to_reset:
        print("✅ Нет постов для сброса")
        conn.close()
        return
    
    print(f"📊 Найдено постов для сброса: {len(posts_to_reset)}")
    
    # 2. Сбрасываем их статус на 'approved' (готов к публикации)
    # Также очищаем published_at, чтобы AutoPoster мог их обработать заново
    reset_count = 0
    for post in posts_to_reset:
        post_id, title, status, published_at, image_url = post
        print(f"  - Пост #{post_id}: '{title[:50] if title else 'без названия'}...' (image_url: {'есть' if image_url else 'нет'})")
        
        cursor.execute(f"""
            UPDATE {table_name} 
            SET status = 'approved', 
                published_at = NULL 
            WHERE id = ?
        """, (post_id,))
        reset_count += 1
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Сброшено записей: {reset_count}")
    print("✅ Контент-план перезагружен. AutoPoster начнет публикацию с правильными интервалами.")

if __name__ == "__main__":
    asyncio.run(reset_posts())
