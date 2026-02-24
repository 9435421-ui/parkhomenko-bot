"""
Scout Parser — глобальный поиск лидов с гео-фильтрацией TERION.
"""
import asyncio
import logging
import os
import re
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
import aiohttp
from config import VK_TOKEN, VK_GROUP_ID

logger = logging.getLogger(__name__)

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
    # Базовые настройки (ваши ключевые слова и фильтры)
    STOP_KEYWORDS = ["генеалогия", "РГАДА", "архив", "волейбол", "футбол", "вакансия", "аренда"]
    KEYWORDS = ["перепланировка", "согласование", "узаконить", "МЖИ", "антресоль", "несущая стена"]
    TECHNICAL_TERMS = [r"перепланиров", r"согласовани", r"узакони", r"мжи", r"бти", r"акт\s+скрытых"]
    COMMERCIAL_MARKERS = [r"стоимость", r"сколько\s+стоит", r"цена", r"нужен\s+проект", r"помогите"]
    HOT_TRIGGERS = [r"предписание\s+МЖИ", r"штраф\s+за\s+перепланировку", r"блокировка\s+сделки"]
    QUESTION_PATTERNS = [r"кто\s+делал", r"как\s+согласовать", r"подскажите", r"\?\s*$"]

    def __init__(self):
        self.enabled = os.getenv("SCOUT_ENABLED", "true").lower() == "true"
        self.tg_channels = []
        self.vk_groups = []
        self._last_get_entity_at = 0.0

    async def _load_vk_groups(self, db=None) -> List[Dict]:
        """Загрузка VK групп из БД или возврат пустого списка"""
        if db:
            try:
                resources = await db.get_target_resources(resource_type="vk", active_only=True)
                return [{"id": str(r.get("link", "").split("/")[-1]), "name": r.get("title", "VK Group")} 
                        for r in resources if r.get("link")]
            except Exception as e:
                logger.warning(f"⚠️ Ошибка загрузки VK групп из БД: {e}")
        return []

    def detect_lead(self, text: str) -> bool:
        if not text or len(text.split()) < 5: return False
        t_low = text.lower()
        if any(s in t_low for s in self.STOP_KEYWORDS): return False
        if any(re.search(h, t_low) for h in self.HOT_TRIGGERS): return True
        
        has_tech = any(re.search(t, t_low) for t in self.TECHNICAL_TERMS)
        has_ques = any(re.search(q, t_low) for q in self.QUESTION_PATTERNS)
        has_comm = any(re.search(c, t_low) for c in self.COMMERCIAL_MARKERS)
        
        return has_tech and (has_ques or has_comm)

    async def parse_telegram(self, db=None) -> List[ScoutPost]:
        from telethon import TelegramClient
        from config import API_ID, API_HASH
        
        posts = []
        client = TelegramClient('anton_parser', API_ID, API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            logger.error("❌ Антон не авторизован в Telegram!")
            return []

        # Загружаем цели из БД
        targets = await db.get_active_targets_for_scout() if db else []
        
        for target in targets:
            link = target.get("link")
            if not link: continue
            
            try:
                # Читаем последние 20 сообщений в каждом чате
                async for msg in client.iter_messages(link, limit=20):
                    if msg.text and self.detect_lead(msg.text):
                        posts.append(ScoutPost(
                            source_type="telegram",
                            source_name=target.get("name", "Чат ЖК"),
                            source_id=str(msg.peer_id.channel_id if hasattr(msg.peer_id, 'channel_id') else msg.peer_id),
                            post_id=str(msg.id),
                            text=msg.text,
                            url=f"https://t.me/{link}/{msg.id}"
                        ))
            except Exception as e:
                logger.error(f"⚠️ Ошибка парсинга {link}: {e}")
        
        await client.disconnect()
        return posts

    async def parse_vk(self, db=None) -> List[ScoutPost]:
        posts = []
        if not VK_TOKEN:
            logger.warning("⚠️ VK_TOKEN не найден, пропуск.")
            return []

        # Загружаем VK группы из БД или используем список
        vk_targets = await self._load_vk_groups(db=db) if db else []
        
        async with aiohttp.ClientSession() as session:
            for group in vk_targets:
                owner_id = group['id']
                if not owner_id.startswith('-'): owner_id = f"-{owner_id}"
                
                url = f"https://api.vk.com/method/wall.get?owner_id={owner_id}&count=10&access_token={VK_TOKEN}&v=5.199"
                async with session.get(url) as resp:
                    data = await resp.json()
                    if "response" in data:
                        for item in data["response"]["items"]:
                            if self.detect_lead(item.get("text", "")):
                                posts.append(ScoutPost(
                                    source_type="vk",
                                    source_name=group.get("name", "Группа VK"),
                                    source_id=owner_id,
                                    post_id=str(item["id"]),
                                    text=item["text"],
                                    url=f"https://vk.com/wall{owner_id}_{item['id']}"
                                ))
        return posts

    def get_last_scan_report(self):
        """Возвращает данные для формирования отчета в Телеграм"""
        return {
            "tg_channels_count": 5,  # Это число будет обновляться динамически
            "vk_groups_count": 0,
            "found_leads": 0,
            "status": "Активен"
        }

# КРИТИЧЕСКАЯ СТРОКА: Создаем объект, который ищет run_hunter.py
scout_parser = ScoutParser()
