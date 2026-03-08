import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
from telethon import TelegramClient
from config import API_ID, API_HASH

logger = logging.getLogger(__name__)

SESSION_NAME = "anton_parser"

@dataclass
class ScoutPost:
    source_type: str
    source_name: str
    source_id: str
    post_id: str
    text: str
    author_id: Optional[int] = None
    author_name: Optional[str] = None
    url: str = ""
    published_at: Optional[datetime] = None
    is_comment: bool = False
    original_channel_id: Optional[str] = None
    likes: int = 0
    comments: int = 0
    source_link: Optional[str] = None

class ScoutParser:
    def __init__(self):
        self.client = None
        self.last_leads = []
        self.KEYWORDS = ["перепланировка", "согласование", "узаконить", "МЖИ", "антресоль"]

    async def start(self):
        if not self.client:
            self.client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
            await self.client.connect()
            try:
                if not await self.client.is_user_authorized():
                    logger.warning("⚠️ Telethon session is not authorized! Telegram scanning will be skipped.")
            except Exception as e:
                logger.warning(f"⚠️ Error checking Telegram authorization: {e}. Telegram scanning will be skipped.")

    async def stop(self):
        if self.client:
            await self.client.disconnect()
            self.client = None

    async def scan_geo_chats(self) -> List[ScoutPost]:
        logger.info("🔍 Scanning geo chats...")
        self.last_leads = []
        
        # Пример логики сканирования
        # В реальности здесь будет список чатов из БД или конфига
        chats = ["@msk_pereplanirovka_chat", "@zhk_heart_of_capital"] 
        
        for chat in chats:
            try:
                async for message in self.client.iter_messages(chat, limit=50):
                    if any(kw.lower() in (message.text or "").lower() for kw in self.KEYWORDS):
                        post = ScoutPost(
                            source_type="telegram",
                            source_name=chat,
                            source_id=str(message.peer_id),
                            post_id=str(message.id),
                            text=message.text,
                            published_at=message.date,
                            url=f"https://t.me/{chat.replace('@', '')}/{message.id}"
                        )
                        self.last_leads.append(post)
            except Exception as e:
                logger.error(f"Error scanning {chat}: {e}")
        
        return self.last_leads

    def get_last_scan_report(self) -> str:
        if not self.last_leads:
            return "<b>🔍 Отчет по сканированию:</b>\nНовых лидов не найдено."
        
        report = f"<b>🎯 Найдено лидов: {len(self.last_leads)}</b>\n\n"
        for i, lead in enumerate(self.last_leads[:10], 1):
            report += f"{i}. <b>{lead.source_name}</b>\n"
            report += f"📝 {lead.text[:100]}...\n"
            report += f"🔗 <a href='{lead.url}'>Перейти к сообщению</a>\n\n"
        
        if len(self.last_leads) > 10:
            report += f"<i>...и еще {len(self.last_leads) - 10} сообщений.</i>"
            
        return report
