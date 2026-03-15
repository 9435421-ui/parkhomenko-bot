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
from database.db import Database

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
        self.db = Database()
        self.last_leads = []
        self.KEYWORDS = ["перепланировка", "согласование", "узаконить", "МЖИ", "антресоль"]
        self.VK_GROUPS = []  # Теперь будет заполняться из БД

    async def start(self):
        from config import API_ID, API_HASH
        if API_ID and API_HASH:
            if not self.client:
                self.client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
                await self.client.connect()
        else:
            logger.warning("⚠️ TG_API_ID/API_HASH не заданы — Telegram-парсинг отключён")
            self.client = None
        
        if not self.db.conn:
            await self.db.connect()

    async def stop(self):
        if self.client:
            await self.client.disconnect()
            self.client = None
        if self.db.conn:
            await self.db.close()

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
        self.last_leads = []
        
        # Подключаемся к БД если еще не подключены
        if not self.db.conn:
            await self.db.connect()
        
        try:
            vk_groups = await self.db.get_active_targets_for_scout(platform='vk')
            logger.info(f"📊 Загружено VK групп из БД: {len(vk_groups)}")
        except Exception as e:
            logger.error(f"📍 Error reading VK groups from DB: {e}")
            vk_groups = []
        
        # Логируем количество групп
        logger.info(f"🔍 Сканирование {len(vk_groups)} VK групп...")
        
        # Если нет групп, возвращаем пустой результат
        if not vk_groups:
            logger.warning("⚠️ No VK groups found in database (is_active=1)")
            return self.last_leads
        
        for group in vk_groups:
            link = group.get('link', '')
            title = group.get('title', link)
            
            # Извлекаем числовой ID из link (например из 'vk.com/club225569022' получаем 225569022)
            group_id = self._extract_vk_group_id(link)
            if not group_id:
                logger.warning(f"⚠️ Could not extract group ID from link: {link}")
                continue
            
            try:
                posts = await self._get_vk_posts(group_id)
                for post in posts:
                    # Проверяем пост на лид
                    lead_type = self.detect_lead(post.get('text', ''))
                    if lead_type:
                        scout_post = ScoutPost(
                            source_type="vk",
                            source_name=title,
                            source_id=group_id,
                            post_id=str(post.get('id', '')),
                            text=post.get('text', ''),
                            published_at=datetime.fromtimestamp(post.get('date', 0)),
                            url=f"https://vk.com/club{group_id}?w=wall-{group_id}_{post.get('id', '')}",
                        )
                        self.last_leads.append(scout_post)
                    
                    # Проверяем комментарии к посту
                    comments = await self._get_vk_comments(group_id, post.get('id', 0))
                    for comment in comments:
                        lead_type = self.detect_lead(comment.get('text', ''))
                        if lead_type:
                            scout_post = ScoutPost(
                                source_type="vk",
                                source_name=title,
                                source_id=group_id,
                                post_id=f"{post.get('id', '')}_comment_{comment.get('id', '')}",
                                text=comment.get('text', ''),
                                published_at=datetime.fromtimestamp(comment.get('date', 0)),
                                url=f"https://vk.com/club{group_id}?w=wall-{group_id}_{post.get('id', '')}&reply={comment.get('id', '')}",
                                is_comment=True,
                            )
                            self.last_leads.append(scout_post)
            except Exception as e:
                logger.error(f"Error scanning VK group {title} (ID: {group_id}): {e}")
        
        logger.info(f"✅ VK groups scan complete: {len(self.last_leads)} leads found")
        return [{"text": p.text, "url": p.url, "source": p.source_name} for p in self.last_leads]

    def _extract_vk_group_id(self, link: str) -> Optional[str]:
        """
        Извлекает числовой ID группы из link.
        Примеры:
        - 'vk.com/club225569022' → '225569022'
        - 'vk.com/pereplanirovka_msk' → 'pereplanirovka_msk' (стратегия fallback)
        - 'https://vk.com/club123456' → '123456'
        """
        if not link:
            return None
        
        # Убираем протокол и www если есть
        link = re.sub(r'^(https?://)?(www\.)?', '', link)
        
        # Если есть 'club' - это числовой ID
        if 'club' in link:
            # Например: club225569022 или vk.com/club225569022
            match = re.search(r'club(\d+)', link)
            if match:
                return match.group(1)
        
        # Если есть 'public' - это тоже числовой ID
        if 'public' in link:
            match = re.search(r'public(\d+)', link)
            if match:
                return match.group(1)
        
        # Fallback: просто берем имя группы (например pereplanirovka_msk)
        # Это может быть короткое имя группы вместо ID
        match = re.search(r'vk\.com/([a-zA-Z0-9_]+)', link)
        if match:
            return match.group(1)
        
        return None

    async def _get_vk_posts(self, group_id: str, count: int = 50) -> List[Dict]:
        """Получение постов из группы ВКонтакте"""
        from config import VK_TOKEN
        if not VK_TOKEN:
            return []
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    "https://api.vk.com/method/wall.get",
                    params={
                        "owner_id": f"-{group_id}",
                        "count": count,
                        "filter": "all",
                        "access_token": VK_TOKEN,
                        "v": "5.199"
                    },
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    data = await resp.json()
                    if "error" in data:
                        logger.warning(f"VK API error for group {group_id}: {data['error']}")
                        return []
                    return data.get("response", {}).get("items", [])
            except Exception as e:
                logger.error(f"VK posts fetch error for group {group_id}: {e}")
                return []

    async def _get_vk_comments(self, group_id: str, post_id: int, count: int = 100) -> List[Dict]:
        """Получение комментариев к посту ВКонтакте"""
        from config import VK_TOKEN
        if not VK_TOKEN:
            return []
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    "https://api.vk.com/method/wall.getComments",
                    params={
                        "owner_id": f"-{group_id}",
                        "post_id": post_id,
                        "count": count,
                        "sort": "desc",
                        "access_token": VK_TOKEN,
                        "v": "5.199"
                    },
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as resp:
                    data = await resp.json()
                    if "error" in data:
                        return []
                    return data.get("response", {}).get("items", [])
            except Exception as e:
                logger.error(f"VK comments fetch error: {e}")
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


# Создаем экземпляр для совместимости
scout_parser = ScoutParser()
