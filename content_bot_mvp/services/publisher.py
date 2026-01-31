import logging
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.db import db
from services.openai_service import openai_service
from datetime import datetime

logger = logging.getLogger(__name__)

class TelegramPublisher:
    def __init__(self, bot: Bot):
        self.bot = bot

        # Hashtags mapping by brand
        self.hashtags = {
            "Torion": "#торион #перепланировка #москва #согласование",
            "DomGrand": "#domgrand #ремонт #дизайн #строительство"
        }

    async def publish_post(self, post_id: int):
        post = await db.get_post(post_id)
        if not post:
            logger.error(f"Post #{post_id} not found for publication")
            return

        channel_config = await db.get_channel_config(post['target_channel_alias'])
        if not channel_config:
            logger.error(f"Channel config not found for alias {post['target_channel_alias']}")
            return

        # Validation: Mandatory quiz link presence
        cta_start = "torion_main" if post['brand'] == "Torion" else "domgrand"
        if cta_start not in post['body'] and cta_start not in post['cta_link']:
             logger.error(f"Post #{post_id} missing mandatory quiz link for {post['brand']}")
             return False

        # Prepare text with hashtags
        brand_hashtags = self.hashtags.get(post['brand'], "")
        full_text = f"{post['body']}\n\n{brand_hashtags}"

        # Prepare CTA button
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Начать расчет", url=post['cta_link'])]
        ])

        try:
            # Optional image generation
            image_url = None
            if post['image_description']:
                image_url = await openai_service.generate_image(post['image_description'])

            # Publish to Telegram
            if image_url:
                await self.bot.send_photo(
                    chat_id=channel_config['channel_id'],
                    photo=image_url,
                    caption=full_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                await self.bot.send_message(
                    chat_id=channel_config['channel_id'],
                    text=full_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )

            # Mark as published in database
            await db.update_post(post_id, status='published', published_at=datetime.now())

            # Log audit
            await db.add_audit_log(
                action="publish_post",
                bot_name=channel_config['bot_name'],
                channel_id=channel_config['channel_id'],
                status="success",
                details=f"Post #{post_id} published to {post['target_channel_alias']}"
            )

            logger.info(f"✅ Post #{post_id} published successfully to {post['target_channel_alias']}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to publish post #{post_id}: {e}")
            await db.add_audit_log(
                action="publish_post",
                bot_name=channel_config['bot_name'],
                channel_id=channel_config['channel_id'],
                status="error",
                details=f"Error: {str(e)}"
            )
            return False
