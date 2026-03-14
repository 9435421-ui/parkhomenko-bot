"""
Скрипт очистки битых ссылок из базы данных.

Проверяет доступность каналов через Telethon и помечает недоступные как archived.
"""
import asyncio
import logging
from database import db
from services.scout_parser import scout_parser

logger = logging.getLogger("cleanup_broken_targets")


async def check_channel_accessibility(link: str) -> tuple[bool, str]:
    """
    Проверяет доступность канала через Telethon.
    
    Returns:
        (is_accessible, error_message)
    """
    try:
        # Пытаемся получить информацию о канале
        info = await scout_parser.resolve_telegram_link(link)
        if info:
            return True, ""
        return False, "Канал не найден или недоступен"
    except Exception as e:
        error_msg = str(e)
        if "USERNAME_INVALID" in error_msg or "CHANNEL_INVALID" in error_msg:
            return False, "Канал не существует"
        elif "USERNAME_NOT_OCCUPIED" in error_msg:
            return False, "Канал не существует"
        elif "CHAT_ADMIN_REQUIRED" in error_msg:
            return False, "Требуются права администратора"
        else:
            return False, f"Ошибка доступа: {error_msg}"


async def main():
    """Основная функция: проверяет все активные цели и архивирует битые."""
    await db.connect()
    
    try:
        # Получаем все активные цели
        targets = await db.get_target_resources(active_only=True)
        
        if not targets:
            print("📭 Нет активных целей для проверки.")
            return
        
        print(f"🔍 Проверяю {len(targets)} активных целей...\n")
        
        archived_count = 0
        accessible_count = 0
        
        for target in targets:
            link = target.get("link", "")
            target_id = target.get("id")
            title = target.get("title") or link
            
            if not link or "t.me" not in link:
                print(f"⚠️  #{target_id} {title}: пропущен (неверный формат ссылки)")
                continue
            
            print(f"Проверяю: {title} ({link})...", end=" ")
            
            is_accessible, error = await check_channel_accessibility(link)
            
            if is_accessible:
                print("✅ Доступен")
                accessible_count += 1
            else:
                print(f"❌ Недоступен: {error}")
                try:
                    await db.set_target_status(target_id, "archived")
                    archived_count += 1
                    print(f"   → Помечен как archived (ID: {target_id})")
                except Exception as e:
                    print(f"   ⚠️  Ошибка при архивации: {e}")
            
            # Небольшая задержка, чтобы не перегружать API
            await asyncio.sleep(1)
        
        print(f"\n📊 Результаты:")
        print(f"   ✅ Доступных: {accessible_count}")
        print(f"   🗑  Архивировано: {archived_count}")
        print(f"   📋 Всего проверено: {len(targets)}")
        
    except Exception as e:
        logger.exception("cleanup_broken_targets failed")
        print(f"❌ Ошибка: {e}")
    finally:
        await db.conn.close()


if __name__ == "__main__":
    asyncio.run(main())
