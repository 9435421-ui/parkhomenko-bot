"""
Быстрое удаление конкретных битых ссылок из БД.

Удаляет ссылки, которые точно не работают (из логов ошибок).
"""
import asyncio
from database import db

# Список битых ссылок из логов
BROKEN_LINKS = [
    "https://t.me/kvartiry_moskvy",
    "https://t.me/interiors_design",
    "https://t.me/interior_ideas_ru",
    "https://t.me/dizayn_kvartiry",
    "https://t.me/zhiteli_moskvy",
    "https://t.me/zhk_simvol_msk",
    "https://t.me/serdce_stolicy",
    "https://t.me/dynasty_zhk_moscow",
    # Также старые общие каналы, которые не нужны
    "https://t.me/msk_realty_chat",
    "https://t.me/novostroyki_moscow",
    "https://t.me/msk_novostroyki",
    "https://t.me/realtymoscow",
    "https://t.me/remont_chats",
    "https://t.me/pereplanirovka_msk",
    "https://t.me/remont_kvartir_moskva",
    "https://t.me/stroitelstvo_remont",
    "https://t.me/msk_chat_official",
    "https://t.me/zilart_msk",  # Старая ссылка на Зиларт
]


async def main():
    """Удаляет битые ссылки из БД"""
    await db.connect()
    
    try:
        archived_count = 0
        not_found_count = 0
        
        for link in BROKEN_LINKS:
            # Ищем запись по ссылке
            async with db.conn.cursor() as cursor:
                await cursor.execute(
                    "SELECT id, title, status FROM target_resources WHERE link = ?",
                    (link,)
                )
                row = await cursor.fetchone()
                
                if row:
                    target_id = row[0]
                    title = row[1] or link
                    current_status = row[2]
                    
                    if current_status != "archived":
                        await db.set_target_status(target_id, "archived")
                        print(f"✅ Архивирован: {title} ({link})")
                        archived_count += 1
                    else:
                        print(f"⏭️  Уже archived: {title} ({link})")
                else:
                    print(f"⚠️  Не найден в БД: {link}")
                    not_found_count += 1
        
        print(f"\n📊 Результаты:")
        print(f"   🗑  Архивировано: {archived_count}")
        print(f"   ⚠️  Не найдено в БД: {not_found_count}")
        print(f"   📋 Всего проверено: {len(BROKEN_LINKS)}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.conn.close()


if __name__ == "__main__":
    asyncio.run(main())
