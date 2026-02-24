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

    def detect_lead(self, text: str) -> bool:
        if not text or len(text.split()) < 5: return False
        t_low = text.lower()
        if any(s in t_low for s in self.STOP_KEYWORDS): return False
        if any(re.search(h, t_low) for h in self.HOT_TRIGGERS): return True
        
        has_tech = any(re.search(t, t_low) for t in self.TECHNICAL_TERMS)
        has_ques = any(re.search(q, t_low) for q in self.QUESTION_PATTERNS)
        has_comm = any(re.search(c, t_low) for c in self.COMMERCIAL_MARKERS)
        
        return has_tech and (has_ques or has_comm)

    async def parse_telegram(self, db=None):
        # Здесь ваша логика Telethon (сокращено для примера)
        logger.info("📡 Scout: Запуск сканирования Telegram...")
        return []

    async def parse_vk(self, db=None):
        logger.info("📡 Scout: Запуск сканирования VK...")
        return []

# КРИТИЧЕСКАЯ СТРОКА: Создаем объект, который ищет run_hunter.py
scout_parser = ScoutParser()
