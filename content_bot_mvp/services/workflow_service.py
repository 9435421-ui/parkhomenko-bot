from typing import List, Optional
from content_bot_mvp.database.db import db
from datetime import datetime

class ContentWorkflow:
    VALID_STATUSES = ['idea', 'draft', 'review', 'approved', 'scheduled', 'published']

    # Определяем разрешенные переходы
    TRANSITIONS = {
        'idea': ['draft'],
        'draft': ['review', 'idea'],
        'review': ['approved', 'draft'],
        'approved': ['scheduled', 'draft'],
        'scheduled': ['published', 'approved', 'draft'],
        'published': [] # Финальное состояние
    }

    @classmethod
    async def move_to_status(cls, item_id: int, next_status: str, user_id: int) -> bool:
        """Переводит контент на следующий этап с проверкой прав и логики"""

        # Получаем текущий статус айтема
        async with db.conn.execute("SELECT status FROM content_items WHERE id = ?", (item_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False
            current_status = row['status']

        # Проверка валидности перехода
        if next_status not in cls.TRANSITIONS.get(current_status, []):
            print(f"⚠️ Некорректный переход: {current_status} -> {next_status}")
            return False

        # Сама смена статуса в БД
        async with db.conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE content_items SET status = ?, updated_at = ? WHERE id = ?",
                (next_status, datetime.now(), item_id)
            )
            await db.conn.commit()

        await db.log_action(user_id, f"status_change_{next_status}", f"Item ID: {item_id}")
        return True

    @classmethod
    def get_available_transitions(cls, current_status: str) -> List[str]:
        return cls.TRANSITIONS.get(current_status, [])

workflow = ContentWorkflow()
