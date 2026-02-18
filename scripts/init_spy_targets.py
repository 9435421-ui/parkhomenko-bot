import asyncio
import logging
from database import db

logger = logging.getLogger("init_spy_targets")

# =============================================================================
# СТРАТЕГИЯ «ОТКРЫТАЯ ОХОТА»
# =============================================================================
# Мы не пытаемся войти в закрытые ЖК-чаты.
# Вместо этого мониторим КРУПНЫЕ ОТКРЫТЫЕ каналы — тематические форумы,
# новостройки Москвы, ремонт, перепланировки.
#
# Как только в любом из этих каналов кто-то упоминает:
#   ЖК Зиларт / Символ / Сердце Столицы / Династия
#   + слово из контекста проблемы (штраф, предписание, перепланировка, МЖИ…)
# → LeadAnalyzer автоматически классифицирует это как ГОРЯЧИЙ ЛИД и
#   немедленно отправляет карточку с профилем автора Юлии.
#
# Публичные каналы с @username — ScoutParser заходит сам без приглашения.
# Если ссылка не открывается — лог покажет конкретную причину (битая/приватная).
# =============================================================================

INITIAL_TARGETS = [
    # ─── Тематические форумы (перепланировки и закон) ──────────────────────
    {
        "link": "https://t.me/pereplanirovka_msk",
        "title": "Перепланировки Москва",
        "participants_count": 0,
        "geo_tag": "Москва",
    },
    {
        "link": "https://t.me/remont_kvartir_moskva",
        "title": "Ремонт квартир Москва",
        "participants_count": 0,
        "geo_tag": "Москва",
    },
    # ─── Новостройки / недвижимость (крупные агрегаторы) ───────────────────
    {
        "link": "https://t.me/novostroyki_moscow",
        "title": "Новостройки Москвы",
        "participants_count": 4500,
        "geo_tag": "Москва",
    },
    {
        "link": "https://t.me/msk_novostroyki",
        "title": "Новостройки МСК",
        "participants_count": 0,
        "geo_tag": "Москва",
    },
    {
        "link": "https://t.me/nedvizhimost_moskva",
        "title": "Недвижимость Москвы",
        "participants_count": 0,
        "geo_tag": "Москва",
    },
    # ─── Жители Москвы (широкие форумы) ────────────────────────────────────
    {
        "link": "https://t.me/zhiteli_moskvy",
        "title": "Жители Москвы",
        "participants_count": 0,
        "geo_tag": "Москва",
    },
    {
        "link": "https://t.me/novomoskovsky_chat",
        "title": "Новая Москва — чат жителей",
        "participants_count": 0,
        "geo_tag": "Москва",
    },
    # ─── ЖК Зиларт (ЛСР) — если канал публичный ───────────────────────────
    {
        "link": "https://t.me/zilart_msk",
        "title": "ЖК Зиларт",
        "participants_count": 0,
        "geo_tag": "ЖК Зиларт",
        "is_high_priority": True,
    },
    # ─── ЖК Символ (Донстрой) ──────────────────────────────────────────────
    {
        "link": "https://t.me/zhk_simvol_msk",
        "title": "ЖК Символ",
        "participants_count": 0,
        "geo_tag": "ЖК Символ",
        "is_high_priority": True,
    },
    # ─── ЖК Сердце Столицы ─────────────────────────────────────────────────
    {
        "link": "https://t.me/serdce_stolicy",
        "title": "ЖК Сердце Столицы",
        "participants_count": 0,
        "geo_tag": "ЖК Сердце Столицы",
        "is_high_priority": True,
    },
    # ─── ЖК Династия ───────────────────────────────────────────────────────
    {
        "link": "https://t.me/dynasty_zhk_moscow",
        "title": "ЖК Династия",
        "participants_count": 0,
        "geo_tag": "ЖК Династия",
        "is_high_priority": True,
    },
]


async def main():
    await db.connect()
    added = 0
    skipped = 0
    for t in INITIAL_TARGETS:
        try:
            await db.add_target_resource(
                "telegram",
                t["link"],
                title=t.get("title"),
                participants_count=t.get("participants_count", 0),
                status="active",
                geo_tag=t.get("geo_tag"),
                is_high_priority=1 if t.get("is_high_priority") else 0,
            )
            added += 1
            flag = " ⭐ ПРИОРИТЕТНЫЙ" if t.get("is_high_priority") else ""
            print(f"  ✅ Добавлен{flag}: {t['title']} ({t['link']})")
        except Exception as e:
            skipped += 1
            print(f"  ⚠️  Пропущен: {t.get('link')} — {e}")
            logger.warning("add target %s failed: %s", t.get("link"), e)
    await db.conn.close()
    print(f"\nГотово: добавлено {added}, пропущено {skipped}.")
    if skipped:
        print("Пропущенные записи уже есть в БД или произошла ошибка (см. выше).")
    print("\nСтратегия 'Открытая охота': шпион ищет упоминания ЖК Зиларт/Символ/Сердце Столицы/Династия")
    print("в ЛЮБОМ из этих каналов. Горячий лид → немедленно карточка Юлии.")


if __name__ == "__main__":
    asyncio.run(main())
