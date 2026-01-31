import asyncio
import logging
import os
import sys

# Add current directory to path to allow absolute imports if run as script
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from database.db import db
from handlers import post_creation, review
from services.scheduler import scheduler_loop

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    # Load token
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN not found in environment")
        return

    # Initialize bot and dispatcher
    from aiogram import Bot, Dispatcher
    from aiogram.fsm.storage.memory import MemoryStorage

    bot = Bot(token=token, parse_mode="HTML")
    dp = Dispatcher(storage=MemoryStorage())

    # Connect to database
    await db.connect()

    # Include routers
    dp.include_router(post_creation.router)
    dp.include_router(review.router)

    # Start scheduler as a background task
    asyncio.create_task(scheduler_loop(bot))

    logger.info("🚀 Content Bot MVP started")

    try:
        await dp.start_polling(bot)
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(main())
