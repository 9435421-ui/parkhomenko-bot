import asyncio
import logging
from database import db

logger = logging.getLogger("init_spy_targets")

# =============================================================================
# СТРАТЕГИЯ «СНАЙПЕРСКИЙ МОНИТОРИНГ ЖК»
# =============================================================================
# Шпион мониторит каналы конкретных ЖК эконом и бизнес-класса.
# 
# Ключевые возможности:
# 1. Парсинг постов в каналах
# 2. Парсинг комментариев в Discussion Groups (если есть)
# 3. Гео-фильтрация по районам Москвы
# 4. Автоматический ответ Антона в комментариях при обнаружении лида
#
# Как работает:
# - Шпион находит вопрос о перепланировке в посте/комментарии
# - LeadAnalyzer классифицирует как лид (ST-1...ST-4)
# - Антон отвечает прямо в ветке обсуждения (публично)
# - Карточка лида отправляется Юлии в рабочую группу
# =============================================================================

# =============================================================================
# АКТУАЛЬНЫЙ СПИСОК ЦЕЛЕЙ TERION (Обновлено 19.02.2026)
# =============================================================================
# Фокус: ЖК эконом и бизнес-класса с активными чатами обсуждений.
# Шпион мониторит посты И комментарии в Discussion Groups.
# =============================================================================

INITIAL_TARGETS = [
    # ── Приоритетные ЖК (проверенные каналы) ───────────────────────────────
    {
        "link": "https://t.me/nekrasovka_msk",
        "title": "Некрасовка Сообщество",
        "participants_count": 0,
        "geo_tag": "ЮВАО",
        "type": "channel",
    },
    {
        "link": "https://t.me/lyublinskiipark",
        "title": "Люблинский парк официальный",
        "participants_count": 0,
        "geo_tag": "ЮВАО",
        "type": "channel",
    },
    {
        "link": "https://t.me/jkfiligrad",
        "title": "Фили Град",
        "participants_count": 0,
        "geo_tag": "ЗАО",
        "type": "channel",
    },
    {
        "link": "https://t.me/filigradnews",
        "title": "Фили Град Новости",
        "participants_count": 0,
        "geo_tag": "ЗАО",
        "type": "channel",
    },
    {
        "link": "https://t.me/jk_volzhskiy_park",
        "title": "Волжский парк",
        "participants_count": 0,
        "geo_tag": "ЮВАО",
        "type": "channel",
    },
    {
        "link": "https://t.me/salarevolife",
        "title": "Саларьево Лайф",
        "participants_count": 0,
        "geo_tag": "НАО (Новая Москва)",
        "type": "channel",
    },
    {
        "link": "https://t.me/mitino2much",
        "title": "Митино О2",
        "participants_count": 0,
        "geo_tag": "СЗАО/МО",
        "type": "channel",
    },
    {
        "link": "https://t.me/skolkovo_residences_uk_kc",
        "title": "Сколково Парк",
        "participants_count": 0,
        "geo_tag": "ЗАО/Можайский",
        "type": "channel",
    },
    {
        "link": "https://t.me/Brateevo_street",
        "title": "Братеево",
        "participants_count": 0,
        "geo_tag": "ЮАО",
        "type": "channel",
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
        "\n✅ Стратегия «Снайперский мониторинг ЖК» активирована.\n"
        "Шпион будет мониторить посты и комментарии в Discussion Groups.\n"
        "При обнаружении лида → Антон отвечает публично в ветке обсуждения."
    )


if __name__ == "__main__":
    asyncio.run(main())
