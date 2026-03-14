"""
Скрипт для архивации нежелательных целей шпиона.

Архивирует цели, содержащие ключевые слова "jail", "топор" и другие нежелательные.
"""
import asyncio
import logging
from database import db

logger = logging.getLogger(__name__)

# Ключевые слова для поиска неправильных целей
UNWANTED_KEYWORDS = [
    "jail",
    "топор",
]


async def archive_unwanted():
    """Архивирует нежелательные цели в базе данных."""
    await db.connect()
    
    try:
        # Получаем все цели из БД
        async with db.conn.cursor() as cursor:
            await cursor.execute("""
                SELECT id, link, title, status, notes 
                FROM target_resources 
                WHERE (type = 'telegram' OR platform = 'telegram')
                AND status != 'archived'
            """)
            targets = await cursor.fetchall()
        
        archived_count = 0
        
        for target in targets:
            target_dict = dict(target)
            link = (target_dict.get("link") or "").lower()
            title = (target_dict.get("title") or "").lower()
            notes = (target_dict.get("notes") or "").lower()
            
            # Проверяем на наличие нежелательных ключевых слов
            is_unwanted = False
            found_keywords = []
            
            for keyword in UNWANTED_KEYWORDS:
                if keyword in link or keyword in title or keyword in notes:
                    is_unwanted = True
                    found_keywords.append(keyword)
            
            if is_unwanted:
                target_id = target_dict.get("id")
                await db.set_target_status(target_id, "archived")
                archived_count += 1
                print(f"✅ Архивирована цель: {target_dict.get('title')} ({target_dict.get('link')})")
                print(f"   Найдены ключевые слова: {', '.join(found_keywords)}")
        
        if archived_count > 0:
            print(f"\n📊 Всего архивировано: {archived_count} целей")
        else:
            print("\n✅ Нежелательных целей для архивации не найдено!")
        
    except Exception as e:
        logger.error(f"Ошибка при архивации целей: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.conn.close()


if __name__ == "__main__":
    print("🔍 Поиск и архивация нежелательных целей...")
    print("=" * 80)
    asyncio.run(archive_unwanted())
