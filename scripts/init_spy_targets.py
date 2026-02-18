import asyncio
import logging
from database import db

logger = logging.getLogger("init_spy_targets")

# =============================================================================
# СТРАТЕГИЯ «ОТКРЫТАЯ ОХОТА»
# =============================================================================
# Шпион НЕ пытается войти в закрытые ЖК-чаты.
# Он мониторит КРУПНЫЕ ОТКРЫТЫЕ каналы по недвижимости, ремонту и дизайну.
#
# Как только в любом из них появляется упоминание приоритетных ЖК:
#   Зиларт / Символ / Сердце Столицы / Династия
#   + контекст проблемы (штраф, предписание, МЖИ, перепланировка…)
# → LeadAnalyzer немедленно классифицирует как ГОРЯЧИЙ ЛИД (ST-4)
#   и шлёт Юлии карточку с профилем автора и проектом ответа.
#
# Публичные @username — ScoutParser заходит сам, авторизация не нужна.
# Если канал не открывается — лог даст точную причину (битая / приватная).
# =============================================================================

INITIAL_TARGETS = [
    # ── Недвижимость и новостройки Москвы ─────────────────────────────────
    {
        "link": "https://t.me/msk_realty_chat",
        "title": "Недвижимость Москвы — чат",
        "participants_count": 0,
        "geo_tag": "Москва",
    },
    {
        "link": "https://t.me/novostroyki_moscow",
        "title": "Новостройки Москвы",
        "participants_count": 0,
        "geo_tag": "Москва",
    },
    {
        "link": "https://t.me/msk_novostroyki",
        "title": "Новостройки МСК",
        "participants_count": 0,
        "geo_tag": "Москва",
    },
    {
        "link": "https://t.me/realtymoscow",
        "title": "Риелторы Москвы",
        "participants_count": 0,
        "geo_tag": "Москва",
    },
    {
        "link": "https://t.me/kvartiry_moskvy",
        "title": "Квартиры Москвы — обсуждения",
        "participants_count": 0,
        "geo_tag": "Москва",
    },
    # ── Ремонт, перепланировки, стройка ───────────────────────────────────
    {
        "link": "https://t.me/remont_chats",
        "title": "Ремонт — чаты",
        "participants_count": 0,
        "geo_tag": "Москва",
    },
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
    {
        "link": "https://t.me/stroitelstvo_remont",
        "title": "Строительство и ремонт",
        "participants_count": 0,
        "geo_tag": "Москва",
    },
    # ── Дизайн интерьеров (там живут люди, которые только начали думать) ──
    {
        "link": "https://t.me/interiors_design",
        "title": "Дизайн интерьеров",
        "participants_count": 0,
        "geo_tag": "Москва",
    },
    {
        "link": "https://t.me/interior_ideas_ru",
        "title": "Идеи интерьера",
        "participants_count": 0,
        "geo_tag": "Москва",
    },
    {
        "link": "https://t.me/dizayn_kvartiry",
        "title": "Дизайн квартиры",
        "participants_count": 0,
        "geo_tag": "Москва",
    },
    # ── Жители Москвы — широкие форумы ────────────────────────────────────
    {
        "link": "https://t.me/zhiteli_moskvy",
        "title": "Жители Москвы",
        "participants_count": 0,
        "geo_tag": "Москва",
    },
    {
        "link": "https://t.me/msk_chat_official",
        "title": "Москва — общий чат",
        "participants_count": 0,
        "geo_tag": "Москва",
    },
    # ── Приоритетные ЖК — если каналы публичны ────────────────────────────
    # Помечены is_high_priority=True → при совпадении скрипт гарантирует ST-4
    {
        "link": "https://t.me/zilart_msk",
        "title": "ЖК Зиларт",
        "participants_count": 0,
        "geo_tag": "ЖК Зиларт",
        "is_high_priority": True,
    },
    {
        "link": "https://t.me/zhk_simvol_msk",
        "title": "ЖК Символ",
        "participants_count": 0,
        "geo_tag": "ЖК Символ",
        "is_high_priority": True,
    },
    {
        "link": "https://t.me/serdce_stolicy",
        "title": "ЖК Сердце Столицы",
        "participants_count": 0,
        "geo_tag": "ЖК Сердце Столицы",
        "is_high_priority": True,
    },
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
    print(
        "\nСтратегия «Открытая охота»: шпион мониторит все каналы выше "
        "и ищет упоминания ЖК Зиларт / Символ / Сердце Столицы / Династия.\n"
        "Совпадение + проблемный контекст → мгновенная карточка Юлии."
    )


if __name__ == "__main__":
    asyncio.run(main())
