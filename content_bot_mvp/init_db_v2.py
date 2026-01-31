import asyncio
from content_bot_mvp.database.db import db

async def init_db():
    await db.connect()

    # Добавление архивного бота
    await db.add_bot_config(
        bot_name="Lad_v_kvartire",
        token="7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw",
        tg_channel_id="@kapremont_channel",
        lead_group_id="-1003370698977",
        platform="TG",
        is_archived=True,
        notes="Архивный бот. Все CTA ссылки должны вести на основной бот ТОРИОН."
    )

    # Добавление админа по умолчанию (замените на ваш ID при необходимости)
    # await db.add_user(telegram_id=USER_ID, username="admin", role="ADMIN")

    print("Database initialized with legacy bot entry.")

if __name__ == "__main__":
    asyncio.run(init_db())
