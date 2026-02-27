"""
Скрипт для активации постов в контент-плане.
Активирует 2 самых свежих поста со статусом 'draft' в статус 'approved'.
"""
import asyncio
import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

from database.db import db
from datetime import datetime


async def activate_latest_posts():
    """Активирует 2 самых свежих поста в контент-плане"""
    try:
        await db.connect()
        
        # Получаем посты со статусом 'draft', отсортированные по дате создания (новые первыми)
        async with db.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT id, title, created_at FROM content_plan WHERE status = 'draft' ORDER BY created_at DESC LIMIT 2"
            )
            posts = await cursor.fetchall()
        
        if not posts:
            print("ℹ️ Нет постов со статусом 'draft' для активации")
            return
        
        print(f"📋 Найдено {len(posts)} постов для активации:")
        
        activated_count = 0
        for post in posts:
            post_id = post[0]
            title = post[1] or f"Пост #{post_id}"
            created_at = post[2]
            
            try:
                # Устанавливаем publish_date на текущее время (чтобы пост мог быть опубликован сразу)
                await db.update_content_plan_entry(
                    post_id=post_id,
                    status='approved',
                    publish_date=datetime.now()
                )
                activated_count += 1
                print(f"✅ Активирован пост #{post_id}: {title[:50]}...")
            except Exception as e:
                print(f"❌ Ошибка активации поста #{post_id}: {e}")
        
        print(f"\n✅ Всего активировано постов: {activated_count}")
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
    finally:
        if db.conn:
            await db.close()


if __name__ == "__main__":
    asyncio.run(activate_latest_posts())
