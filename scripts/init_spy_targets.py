import asyncio
import logging
from database import db

logger = logging.getLogger("init_spy_targets")

# Набор начальных целевых чатов/каналов (примерные публичные ссылки — замените на реальные при необходимости)
INITIAL_TARGETS = [
    {"link": "https://t.me/novostroyki_moscow", "title": "Новостройки Москвы", "participants_count": 4500},
    {"link": "https://t.me/zhk_moscow_forum", "title": "ЖК Москва — обсуждения", "participants_count": 3200},
    {"link": "https://t.me/remont_mastertips", "title": "Ремонт и отделка — советы", "participants_count": 2700},
    {"link": "https://t.me/kvartiry_msk", "title": "Квартиры Москвы", "participants_count": 6100},
    {"link": "https://t.me/stroitelstvo_msk", "title": "Строительство и планировки", "participants_count": 1800},
]

async def main():
    await db.connect()
    added = 0
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
        except Exception as e:
            logger.exception("add target %s failed", t.get("link"))
    await db.conn.close()
    print(f"Initialized {added} targets.")

if __name__ == "__main__":
    asyncio.run(main())

