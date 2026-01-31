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
        'approved': ['scheduled', 'published', 'draft'],
        'scheduled': ['published', 'approved', 'draft'],
        'published': [] # Финальное состояние
    }

    # Маппинг ролей на разрешенные переходы
    ROLE_PERMISSIONS = {
        'AUTHOR': {
            'idea': ['draft'],
            'draft': ['review', 'idea'],
            'review': ['draft'],
            'approved': [],
            'scheduled': [],
            'published': []
        },
        'EDITOR': {
            'idea': ['draft'],
            'draft': ['review', 'idea'],
            'review': ['approved', 'draft'],
            'approved': ['scheduled', 'draft'],
            'scheduled': ['approved', 'draft'],
            'published': []
        },
        'ADMIN': {
            'idea': ['draft'],
            'draft': ['review', 'idea'],
            'review': ['approved', 'draft'],
            'approved': ['scheduled', 'published', 'draft'],
            'scheduled': ['published', 'approved', 'draft'],
            'published': []
        }
    }

    @classmethod
    async def move_to_status(cls, item_id: int, next_status: str, user_id: int, user_role: str) -> bool:
        """Переводит контент на следующий этап с проверкой прав и логики"""

        # Получаем айтем
        async with db.conn.execute("SELECT status, created_by FROM content_items WHERE id = ?", (item_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                return False
            current_status = row['status']
            created_by = row['created_by']

        # Проверка прав доступа (Author может менять только свои)
        if user_role == 'AUTHOR' and created_by != user_id:
            print(f"🚫 Доступ запрещен: Автор {user_id} пытается изменить чужой пост {item_id}")
            return False

        # Проверка разрешенных переходов для роли
        allowed_next_statuses = cls.ROLE_PERMISSIONS.get(user_role, {}).get(current_status, [])
        if next_status not in allowed_next_statuses:
            print(f"⚠️ Некорректный переход для роли {user_role}: {current_status} -> {next_status}")
            return False

        # Дополнительная проверка общей логики переходов (на всякий случай)
        if next_status not in cls.TRANSITIONS.get(current_status, []):
            return False

        # Смена статуса в БД
        async with db.conn.cursor() as cursor:
            await cursor.execute(
                "UPDATE content_items SET status = ?, updated_at = ? WHERE id = ?",
                (next_status, datetime.now(), item_id)
            )
            await db.conn.commit()

        await db.log_action(user_id, f"status_change_{next_status}", f"Item ID: {item_id}", status=next_status)
        return True

    @classmethod
    def get_available_transitions(cls, current_status: str, user_role: str) -> List[str]:
        return cls.ROLE_PERMISSIONS.get(user_role, {}).get(current_status, [])

workflow = ContentWorkflow()
