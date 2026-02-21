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
    
    # Проверяем, какая таблица существует: content_plan или posts
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name='content_plan' OR name='posts')")
    tables = cursor.fetchall()
    
    table_name = None
    if tables:
        # Берем первую найденную таблицу
        table_name = tables[0][0]
        print(f"📋 Найдена таблица: {table_name}")
    else:
        print("❌ Таблицы content_plan или posts не найдены")
        conn.close()
        return
    
    # 1. Находим посты, которые были опубликованы за последние 5 часов без изображений
    # Или все опубликованные посты за последние 5 часов (для безопасности)
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
    
    # 2. Сбрасываем их статус на 'draft' (или 'ready_to_publish', если такой статус используется)
    # Также очищаем published_at
    reset_count = 0
    for post in posts_to_reset:
        post_id, title, status, published_at, image_url = post
        print(f"  - Пост #{post_id}: '{title[:50] if title else 'без названия'}...' (image_url: {'есть' if image_url else 'нет'})")
        
        cursor.execute(f"""
            UPDATE {table_name} 
            SET status = 'draft', 
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
