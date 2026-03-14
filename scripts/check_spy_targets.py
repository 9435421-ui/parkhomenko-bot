"""
Скрипт для проверки и очистки старых целей шпиона из базы данных.

Проверяет target_resources на наличие старых/неправильных целей (например, "Jail", "Топор")
и позволяет их архивировать или удалить.
"""
import asyncio
import logging
from database import db

logger = logging.getLogger(__name__)

# Старые/неправильные цели для проверки
OLD_UNWANTED_TARGETS = [
    "jail",
    "топор",
    "Jail",
    "Топор",
    "JAIL",
    "ТОПОР",
]

# Ключевые слова для поиска неправильных целей
UNWANTED_KEYWORDS = [
    "jail",
    "топор",
]


async def check_targets():
    """Проверяет все цели в базе данных на наличие старых/неправильных записей."""
    await db.connect()
    
    try:
        # Получаем все цели из БД
        async with db.conn.cursor() as cursor:
            await cursor.execute("""
                SELECT id, link, title, status, notes, geo_tag 
                FROM target_resources 
                WHERE type = 'telegram' OR platform = 'telegram'
                ORDER BY id DESC
            """)
            targets = await cursor.fetchall()
        
        print(f"\n📊 Всего целей в БД: {len(targets)}\n")
        print("=" * 80)
        
        unwanted_found = []
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
                unwanted_found.append({
                    "id": target_dict.get("id"),
                    "link": target_dict.get("link"),
                    "title": target_dict.get("title"),
                    "status": target_dict.get("status"),
                    "keywords": found_keywords,
                })
                print(f"⚠️  НАЙДЕНА НЕЖЕЛАТЕЛЬНАЯ ЦЕЛЬ:")
                print(f"   ID: {target_dict.get('id')}")
                print(f"   Название: {target_dict.get('title')}")
                print(f"   Ссылка: {target_dict.get('link')}")
                print(f"   Статус: {target_dict.get('status')}")
                print(f"   Найдены ключевые слова: {', '.join(found_keywords)}")
                print("-" * 80)
            else:
                # Показываем все активные цели для справки
                if target_dict.get("status") == "active":
                    print(f"✅ Активная цель: {target_dict.get('title')} ({target_dict.get('link')})")
        
        if unwanted_found:
            print(f"\n🚨 Найдено нежелательных целей: {len(unwanted_found)}")
            print("\nДля архивации выполните:")
            print("  python scripts/archive_unwanted_targets.py")
        else:
            print("\n✅ Нежелательных целей не найдено!")
            print("Все цели в порядке.")
        
        # Показываем статистику
        async with db.conn.cursor() as cursor:
            await cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM target_resources 
                WHERE type = 'telegram' OR platform = 'telegram'
                GROUP BY status
            """)
            stats = await cursor.fetchall()
            
            print("\n📈 Статистика по статусам:")
            for stat in stats:
                print(f"   {stat['status']}: {stat['count']}")
        
    except Exception as e:
        logger.error(f"Ошибка при проверке целей: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.conn.close()


if __name__ == "__main__":
    asyncio.run(check_targets())
