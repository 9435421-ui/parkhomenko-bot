import asyncio
import sys
import os

# Добавляем корень проекта в путь
sys.path.append(os.getcwd())

from content_bot_mvp.database.db import db
from content_bot_mvp.services.workflow_service import workflow

async def run_tests():
    print("--- Подключение к БД ---", flush=True)
    await db.connect()
    print("--- Подключено ---", flush=True)

    # 1. Создаем тестовый пост
    async with db.conn.cursor() as cursor:
        await cursor.execute(
            "INSERT INTO content_items (title, body, status, created_by, bot_name) VALUES (?, ?, ?, ?, ?)",
            ("Тестовый пост", "Содержание", "idea", 101, "TerionProjectBot")
        )
        item_id = cursor.lastrowid
        await db.conn.commit()
    print(f"✅ Создан тестовый пост ID: {item_id}", flush=True)

    # 2. Тест: Автор переводит в Draft (Разрешено)
    success = await workflow.move_to_status(item_id, 'draft', 101, 'AUTHOR')
    print(f"Test 1 (Author Idea -> Draft): {'PASS' if success else 'FAIL'}", flush=True)

    # 3. Тест: Автор пытается перескочить в Approved (Запрещено)
    success = await workflow.move_to_status(item_id, 'approved', 101, 'AUTHOR')
    print(f"Test 2 (Author Draft -> Approved): {'PASS' if not success else 'FAIL (Jumped!)'}", flush=True)

    # 4. Тест: Другой автор пытается изменить пост (Запрещено)
    success = await workflow.move_to_status(item_id, 'review', 102, 'AUTHOR')
    print(f"Test 3 (Other Author Change): {'PASS' if not success else 'FAIL (Unauthorized!)'}", flush=True)

    # 5. Тест: Автор переводит в Review (Разрешено)
    success = await workflow.move_to_status(item_id, 'review', 101, 'AUTHOR')
    print(f"Test 4 (Author Draft -> Review): {'PASS' if success else 'FAIL'}", flush=True)

    # 6. Тест: Автор пытается сам утвердить свой пост (Запрещено)
    success = await workflow.move_to_status(item_id, 'approved', 101, 'AUTHOR')
    print(f"Test 5 (Author Self-Approve): {'PASS' if not success else 'FAIL (Self-approved!)'}", flush=True)

    # 7. Тест: Editor утверждает пост (Разрешено)
    success = await workflow.move_to_status(item_id, 'approved', 201, 'EDITOR')
    print(f"Test 6 (Editor Approve): {'PASS' if success else 'FAIL'}", flush=True)

    # 8. Тест: Admin публикует пост (Разрешено)
    success = await workflow.move_to_status(item_id, 'published', 999, 'ADMIN')
    print(f"Test 7 (Admin Publish): {'PASS' if success else 'FAIL'}", flush=True)

    # Проверка логов
    async with db.conn.execute("SELECT * FROM audit_log WHERE details LIKE ?", (f"%Item ID: {item_id}%",)) as cursor:
        logs = await cursor.fetchall()
        print(f"✅ Записей в audit_log для поста {item_id}: {len(logs)}", flush=True)
        for log in logs:
            print(f"  - Action: {log['action']}, Status: {log['status']}, User: {log['user_id']}", flush=True)

    await db.conn.close()
    print("--- Тесты завершены ---", flush=True)

if __name__ == "__main__":
    asyncio.run(run_tests())
