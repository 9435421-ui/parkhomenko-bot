import asyncio
import logging
import os
import re
import aiohttp
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

# Ключевые слова для фильтрации лидов
STOP_WORDS = [
    "продам", "сдам", "аренда", "куплю", "ищу квартиру",
    "риелтор", "агентство", "новостройка", "скидка", "акция",
    "подписывайтесь", "переходите по ссылке", "наш сайт",
    "оставьте заявку", "звоните нам", "специальное предложение",
]

HOT_TRIGGERS = [
    r"предписание\s*мжи",
    r"штраф\s+за\s+перепланировку",
    r"блокировка\s+сделки",
    r"узаконить\s+перепланировку",
    r"инспектор\s+мжи",
    r"согласовать\s+перепланировку",
    r"проект\s+перепланировки",
    r"заказать\s+проект",
    r"нужен\s+проект",
    r"кто\s+согласовывал",
    r"нужна\s+помощь.*перепланировк",
    r"перепланировк.*срочно",
]

TECHNICAL_TERMS = [
    r"перепланиров",
    r"согласовани",
    r"узакони",
    r"\bмжи\b",
    r"\bбти\b",
    r"акт\s+скрытых",
    r"снос\s+(стен|подоконн|блока)",
    r"объединен",
    r"нежилое\s+помещен",
    r"план\s+(квартир|помещен)",
    r"мокрая\s+зона",
    r"несущая\s+стена",
    r"демонтаж\s+стен",
    r"перенос\s+кухн",
]

COMMERCIAL_MARKERS = [
    r"сколько\s+стоит",
    r"\bцена\b",
    r"\bстоимость\b",
    r"к\s+кому\s+обратиться",
    r"посоветуйте\s+(компани|специалист|фирм)",
    r"заказать\s+проект",
    r"оформить\s+перепланировку",
    r"согласовал\w*",
    r"узаконил\w*",
    r"кто\s+делал",
    r"кто\s+помогал",
    r"порекомендуйте",
    r"подскажите\s+(компани|специалист)",
]

QUESTION_MARKERS = [
    r"\?\s*$",
    r"подскажите",
    r"помогите",
    r"как\s+(согласовать|узаконить|оформить|сделать)",
    r"кто\s+(согласовывал|оформлял|делал|заказывал|помогал)",
    r"есть\s+кто",
    r"посоветуйте",
    r"нужна\s+помощь",
    r"что\s+делать",
    r"с\s+чего\s+начать",
]

class ScoutParser:
    def __init__(self):
        self.client = None
        self.last_leads = []
        self.KEYWORDS = ["перепланировка", "согласование", "узаконить", "МЖИ", "антресоль"]
        self.VK_GROUPS = ["pereplanirovka_msk", "pereplanirovka_spb"]  # Пример групп ВК

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
        """Сканирование Telegram чатов (требует авторизации Telethon)"""
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

    async def scan_vk_groups(self) -> List[ScoutPost]:
        """Сканирование групп ВКонтакте (не требует авторизации Telethon)"""
        logger.info("🔍 Scanning VK groups...")
        self.last_leads = []
        
        for group in self.VK_GROUPS:
            try:
                posts = await self._get_vk_posts(group)
                for post in posts:
                    # Проверяем пост на лид
                    lead_type = self.detect_lead(post.get('text', ''))
                    if lead_type:
                        scout_post = ScoutPost(
                            source_type="vk",
                            source_name=group,
                            source_id=group,
                            post_id=str(post.get('id', '')),
                            text=post.get('text', ''),
                            published_at=datetime.fromtimestamp(post.get('date', 0)),
                            url=f"https://vk.com/{group}?w=wall{post.get('owner_id', '')}_{post.get('id', '')}"
                        )
                        self.last_leads.append(scout_post)
                    
                    # Проверяем комментарии к посту
                    comments = await self._get_vk_comments(group, post.get('id', 0))
                    for comment in comments:
                        lead_type = self.detect_lead(comment.get('text', ''))
                        if lead_type:
                            scout_post = ScoutPost(
                                source_type="vk",
                                source_name=group,
                                source_id=group,
                                post_id=f"{post.get('id', '')}_comment_{comment.get('id', '')}",
                                text=comment.get('text', ''),
                                published_at=datetime.fromtimestamp(comment.get('date', 0)),
                                url=f"https://vk.com/{group}?w=wall{post.get('owner_id', '')}_{post.get('id', '')}?reply={comment.get('id', '')}",
                                is_comment=True
                            )
                            self.last_leads.append(scout_post)
            except Exception as e:
                logger.error(f"Error scanning VK group {group}: {e}")
        
        return self.last_leads

    async def _get_vk_posts(self, group_id: str, count: int = 50) -> List[Dict]:
        """Получение постов из группы ВКонтакте"""
        # Для реального использования нужно добавить VK API token в config.py
        # и использовать настоящий VK API
        # Пока возвращаем заглушку
        return []

    async def _get_vk_comments(self, group_id: str, post_id: int, count: int = 100) -> List[Dict]:
        """Получение комментариев к посту ВКонтакте"""
        # Для реального использования нужно добавить VK API token в config.py
        # и использовать настоящий VK API
        # Пока возвращаем заглушку
        return []

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

    def detect_lead(self, text: str) -> Optional[str]:
        """Возвращает 'hot', 'warm' или None."""
        if not text or len(text.strip()) < 15:
            return None
        if len(text) > 2000:
            return None
        if self._has_stop_word(text):
            return None
        if self._count_links(text) > 2:
            return None

        # Горячий триггер — безусловный лид
        if self._matches(text, HOT_TRIGGERS):
            return "hot"

        has_tech     = self._matches(text, TECHNICAL_TERMS)
        has_comm     = self._matches(text, COMMERCIAL_MARKERS)
        has_question = self._matches(text, QUESTION_MARKERS)

        # Для VK достаточно технического термина + вопроса/коммерческого маркера
        if has_tech and (has_comm or has_question):
            return "warm"

        # Или просто технический термин в вопросительном сообщении
        if has_tech and "?" in text:
            return "warm"

        return None

    def _matches(self, text: str, patterns: list) -> bool:
        t = text.lower()
        return any(re.search(p, t) for p in patterns)

    def _has_stop_word(self, text: str) -> bool:
        t = text.lower()
        return any(w in t for w in STOP_WORDS)

    def _count_links(self, text: str) -> int:
        return len(re.findall(r"https?://|vk\.com/|t\.me/", text))
