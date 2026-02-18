import asyncio
import logging
from database import db

logger = logging.getLogger("init_spy_targets")

# Целевые чаты ЖК для мониторинга.
#
# ВАЖНО: Telegram делит чаты на публичные (есть @username — бот входит сам)
# и приватные (ссылка вида t.me/+HASH — бот должен быть УЧАСТНИКОМ чата заранее).
#
# Публичные (@username) — ScoutParser может войти автоматически.
# Приватные (t.me/+...) — добавьте аккаунт-парсер (TELEGRAM_PHONE) в чат вручную,
#   затем вставьте сюда ссылку-приглашение или числовой chat_id.
#
# Как узнать chat_id закрытой группы:
#   1. Перешлите любое сообщение из группы боту @userinfobot.
#   2. Или вставьте invite-ссылку сюда — парсер попробует принять приглашение.
INITIAL_TARGETS = [
    # --- Публичные каналы / чаты (можно проверить в браузере) ---
    {
        "link": "https://t.me/zilart_official",
        "title": "ЖК Зиларт (официальный)",
        "participants_count": 0,
        "note": "Публичный канал ЖК Зиларт от ЛСР",
    },
    {
        "link": "https://t.me/symbol_zhk",
        "title": "ЖК Символ (официальный)",
        "participants_count": 0,
        "note": "Публичный канал ЖК Символ от Донстрой",
    },
    {
        "link": "https://t.me/serdce_stolicy",
        "title": "ЖК Сердце Столицы",
        "participants_count": 0,
        "note": "Публичный канал ЖК Сердце Столицы",
    },
    # --- Жители / форумы (публичные username-группы, наиболее активны) ---
    {
        "link": "https://t.me/zhk_zilart_zhiteli",
        "title": "Жители ЖК Зиларт",
        "participants_count": 0,
        "note": "Группа жителей Зиларт — ищем по ключевым словам перепланировка/согласование",
    },
    {
        "link": "https://t.me/dynasty_zhk",
        "title": "ЖК Династия",
        "participants_count": 0,
        "note": "Группа жителей ЖК Династия",
    },
    # --- Тематические публичные каналы (запасные источники) ---
    {
        "link": "https://t.me/novostroyki_moscow",
        "title": "Новостройки Москвы",
        "participants_count": 4500,
        "note": "Публичный канал — новостройки Москвы",
    },
    {
        "link": "https://t.me/pereplanirovka_msk",
        "title": "Перепланировка Москва",
        "participants_count": 0,
        "note": "Тематический канал по перепланировкам",
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
                participants_count=t.get("participants_count"),
                status="active",
            )
            added += 1
            print(f"  ✅ Добавлен: {t['title']} ({t['link']})")
        except Exception as e:
            skipped += 1
            print(f"  ⚠️  Пропущен: {t.get('link')} — {e}")
            logger.warning("add target %s failed: %s", t.get("link"), e)
    await db.conn.close()
    print(f"\nГотово: добавлено {added}, пропущено {skipped}.")
    if skipped:
        print("Пропущенные записи уже есть в БД или произошла ошибка (см. выше).")

if __name__ == "__main__":
    asyncio.run(main())

