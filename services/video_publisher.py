"""
services/video_publisher.py
Публикация видео в TG и VK
"""
import os
import logging
from pathlib import Path
from datetime import datetime
from aiogram import Bot
from aiogram.types import FSInputFile

logger = logging.getLogger(__name__)

class VideoPublisher:
    """Публикация видео"""
    
    def __init__(self, bot: Bot = None):
        self.bot = bot
    
    async def publish_to_telegram(
        self,
        channel_id: int,
        video_path: str,
        caption: str = "",
        title: str = ""
    ) -> bool:
        """Опубликовать видео в TG"""
        if not self.bot:
            logger.error("❌ Bot instance not provided")
            return False
        
        try:
            if not os.path.exists(video_path):
                logger.error(f"❌ Видео не найдено: {video_path}")
                return False
            
            full_caption = caption
            if title:
                full_caption = f"<b>{title}</b>\n\n{caption}"
            
            video_file = FSInputFile(video_path)
            
            await self.bot.send_video(
                chat_id=channel_id,
                video=video_file,
                caption=full_caption,
                parse_mode="HTML"
            )
            
            logger.info(f"✅ Видео опубликовано в TG {channel_id}")
            return True
        
        except Exception as e:
            logger.error(f"❌ Ошибка TG: {e}")
            return False

publisher = VideoPublisher()
