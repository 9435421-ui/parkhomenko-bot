#!/usr/bin/env python3
import os, sys, asyncio, logging
sys.path.insert(0, '/root/PARKHOMENKO_BOT')
from dotenv import load_dotenv
load_dotenv('/root/PARKHOMENKO_BOT/.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    from aiogram import Bot, Dispatcher
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.client.default import DefaultBotProperties
    from config import CONTENT_BOT_TOKEN
    from handlers.content_bot import content_router
    from database.db import db
    from utils.bot_config import set_content_bot

    await db.connect()
    bot = Bot(token=CONTENT_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    set_content_bot(bot)

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(content_router)

    me = await bot.get_me()
    logger.info(f"🚀 Контент-бот: @{me.username}")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
