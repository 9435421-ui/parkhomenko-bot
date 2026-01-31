import asyncio
from content_bot_mvp.database.db import db

async def init_db():
    await db.connect()

    # 1. Добавление основного контент-бота
    await db.add_bot_config(
        bot_name="domgrad_content",
        token="8123470161:AAGRFvjNWlp2mQaAt19qO8bnVowZg4FTJ64",
        tg_channel_id="@torion_channel",
        channel_alias="torion_main",
        brand="TORION",
        platform="TG",
        notes="Основной канал ТОРИОН"
    )

    await db.add_bot_config(
        bot_name="domgrad_content",
        token="8123470161:AAGRFvjNWlp2mQaAt19qO8bnVowZg4FTJ64",
        tg_channel_id="-1002628548032",
        channel_alias="domgrand",
        brand="TORION",
        platform="TG",
        notes="Канал DomGrand"
    )

    # 2. Добавление архивного бота
    await db.add_bot_config(
        bot_name="Lad_v_kvartire",
        token="ARCHIVED",
        tg_channel_id="@kapremont_channel",
        lead_group_id="-1003370698977",
        platform="TG",
        is_archived=True,
        notes="Архивный бот. Все CTA ссылки должны вести на основной бот ТОРИОН."
    )

    print("Database initialized with current production bot entries.")

if __name__ == "__main__":
    asyncio.run(init_db())
