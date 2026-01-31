import asyncio
import logging
from .publisher import TelegramPublisher
from ..database.db import db

logger = logging.getLogger(__name__)

async def scheduler_loop(bot):
    publisher = TelegramPublisher(bot)
    logger.info("⏰ Content Scheduler started")

    while True:
        try:
            # Check for posts that should be published now
            scheduled_posts = await db.get_scheduled_posts()

            for post in scheduled_posts:
                logger.info(f"🚀 Publishing scheduled post #{post['id']}")
                await publisher.publish_post(post['id'])

        except Exception as e:
            logger.error(f"❌ Error in scheduler loop: {e}")

        # Poll every 60 seconds
        await asyncio.sleep(60)
