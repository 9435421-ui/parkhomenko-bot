<<<<<<< HEAD
=======
"""
Scout Parser — глобальный поиск лидов с гео-фильтрацией TERION.
"""
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
import asyncio
import logging
import os
import re
<<<<<<< HEAD
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
from telethon import TelegramClient
from config import API_ID, API_HASH
from database.db import Database

logger = logging.getLogger(__name__)

SESSION_NAME = "anton_parser"

=======
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
import aiohttp
from config import VK_TOKEN, VK_GROUP_ID

logger = logging.getLogger(__name__)

>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
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

<<<<<<< HEAD
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
                            url=f"https://vk.com/club{group_id}?w=wall-{group_id}_{post.get('id', '')}"
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
                                is_comment=True
                            )
                            self.last_leads.append(scout_post)
            except Exception as e:
                logger.error(f"Error scanning VK group {title} (ID: {group_id}): {e}")
        
        logger.info(f"✅ VK groups scan complete: {len(self.last_leads)} leads found")
        return self.last_leads

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
=======
class ScoutParser:
    """
    Scout Parser — снайперский мониторинг жилых ЖК с Data-Driven Scout.
    
    Использует:
    - Фильтрацию по платформе (telegram/vk)
    - Приоритетные ЖК (is_high_priority)
    - Гео-теги для приоритизации
    - Инкрементальный парсинг через last_post_id
    """
    
    # Базовые настройки (ключевые слова и фильтры)
    STOP_KEYWORDS = ["генеалогия", "РГАДА", "архив", "волейбол", "футбол", "вакансия", "аренда"]
    
    # Расширенные ключевые слова (из "Жюль")
    KEYWORDS = [
        "перепланировка", "согласование", "узаконить", "МЖИ", "антресоль", "несущая стена",
        "перепланировку", "согласовать", "проект перепланировки", "перепланировки",
        "нежилое помещение", "коммерция", "отдельный вход", "общепит", "кафе", "офис",
        "изменение назначения"
    ]
    
    # Технические термины (расширенные из "Жюль")
    TECHNICAL_TERMS = [
        r"перепланиров", r"согласовани", r"узакони", r"мжи", r"бти", r"акт\s+скрытых",
        r"предписание\s+МЖИ", r"штраф\s+за\s+перепланировку", r"акт\s+скрытых\s+работ",
        r"проект\s+СРО", r"согласие\s+соседей", r"мокрая\s+зона", r"снос\s+(стен|подоконн|блока)",
        r"объединен", r"нежилое\s+помещен", r"проект\s+перепланировки", r"план\s+(квартир|помещен)"
    ]
    
    # Коммерческие маркеры (расширенные из "Жюль")
    COMMERCIAL_MARKERS = [
        r"стоимость", r"сколько\s+стоит", r"цена", r"нужен\s+проект", r"помогите",
        r"сроки", r"кто\s+делал", r"к\s+кому\s+обратиться", r"предписание",
        r"инспектор", r"заказать\s+проект", r"оформить\s+перепланировку", r"согласовал\w*", r"узаконил\w*"
    ]
    
    # Горячие триггеры (расширенные из "Жюль")
    HOT_TRIGGERS = [
        r"предписание\s+МЖИ", r"штраф\s+за\s+перепланировку", r"блокировка\s+сделки",
        r"узаконить\s+перепланировку", r"инспектор\s+МЖИ", r"согласовать\s+перепланировку",
        r"проект\s+перепланировки", r"заказать\s+проект", r"нужен\s+проект", r"кто\s+согласовывал"
    ]
    
    # Паттерны вопросов (расширенные из "Жюль")
    QUESTION_PATTERNS = [
        r"кто\s+делал", r"как\s+согласовать", r"подскажите", r"\?\s*$",
        r"кто\s+(согласовывал|оформлял|делал|заказывал)", r"как\s+(согласовать|узаконить|оформить|сделать)",
        r"подскажите\s+(,\s*)?(кто|как|где|можно)", r"посоветуйте\s+(,\s*)?(кто|кого|как)",
        r"соседи\s*[,:]", r"кто\s*[-–]?\s*нибудь", r"есть\s+ли\s+кто", r"может\s+кто\s+(знает|сталкивался|делал)",
        r"где\s+(согласовывал|оформлял)", r"можно\s+ли\s+(сносит|объединят|переносит)"
    ]
    
    # Приоритетные ЖК для мониторинга (из "Жюль")
    PRIORITY_ZHK_NAMES = [
        "сердце столицы", "символ", "зиларт", "пресня сити", "сити", "башн", "династия"
    ]
    
    # Черный список рекламных фраз (Анти-Спам)
    AD_STOP_WORDS = [
        "подпишись", "подписывайтесь", "наш канал", "наш телеграм", "наш тг",
        "выплата", "заработок", "канал о недвижимости", "заходи в группу",
        "вступай в группу", "присоединяйся", "реклама", "промокод", "скидка",
        "акция", "распродажа", "бесплатно получить", "только сегодня", "ограниченное предложение"
    ]

    def __init__(self):
        self.enabled = os.getenv("SCOUT_ENABLED", "true").lower() == "true"
        self.tg_channels = []
        self.vk_groups = []
        self._last_get_entity_at = 0.0
        # Отчет последнего скана (для get_last_scan_report)
        self.last_scan_report = []
        self.last_scan_at: Optional[datetime] = None

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

    async def _detect_lead_async(
        self, 
        text: str, 
        platform: str = "telegram",
        sender_type: Optional[str] = None,
        author_id: Optional[int] = None,
        url: str = "",
        db=None
    ) -> bool:
        """
        Асинхронная версия detect_lead для проверки истории контактов через БД.
        """
        # Сначала проверяем историю контактов (если есть author_id и БД)
        if author_id and db:
            try:
                has_recent_contact = await db.check_recent_contact(str(author_id), hours=48)
                if has_recent_contact:
                    logger.debug(f"🚫 Уже писали пользователю {author_id} в последние 48 часов — пропущено")
                    return False
            except Exception as e:
                logger.debug(f"⚠️ Ошибка проверки истории контактов: {e}")
                # Продолжаем, если проверка не удалась
        
        # Вызываем синхронную версию detect_lead
        return self.detect_lead(text, platform, sender_type, author_id, url, db)
    
    def detect_lead(
        self, 
        text: str, 
        platform: str = "telegram",
        sender_type: Optional[str] = None,
        author_id: Optional[int] = None,
        url: str = "",
        db=None
    ) -> bool:
        """
        Интеллектуальный фильтр для детекции лидов с защитой от спама и ботов.
        Использует расширенные ключевые слова и триггеры из "Жюль".
        
        Args:
            text: Текст сообщения
            platform: Платформа ("telegram" или "vk")
            sender_type: Тип отправителя ("channel", "user", None)
            author_id: ID автора сообщения (для проверки истории)
            url: URL сообщения (для детекции ссылок)
            db: Объект БД (для проверки истории контактов)
        
        Returns:
            True если сообщение является лидом и прошло все фильтры
        """
        if not text or len(text.split()) < 5:
            return False
        
        t_low = text.lower()
        
        # ── ФИЛЬТР 1: Исключение каналов ────────────────────────────────────────
        # Если сообщение от имени канала (не от пользователя) — игнорируем
        if sender_type == "channel" or sender_type == "broadcast":
            logger.debug("🚫 Сообщение от канала — пропущено")
            return False
        
        # ── ФИЛЬТР 2: Стоп-слова (базовые) ────────────────────────────────────────
        if any(s in t_low for s in self.STOP_KEYWORDS):
            logger.debug("🚫 Стоп-слово обнаружено — пропущено")
            return False
        
        # ── ФИЛЬТР 3: Черный список рекламных фраз (AD_STOP_WORDS) ───────────────
        if any(ad_word in t_low for ad_word in self.AD_STOP_WORDS):
            logger.debug("🚫 Рекламная фраза обнаружена — пропущено")
            return False
        
        # ── ФИЛЬТР 4: Детектор рекламных ссылок ────────────────────────────────────
        # Подсчитываем количество ссылок в тексте
        url_pattern = r'https?://[^\s]+|t\.me/[^\s]+|vk\.com/[^\s]+'
        urls_found = re.findall(url_pattern, text, re.IGNORECASE)
        
        # Если более 2 ссылок — спам
        if len(urls_found) > 2:
            logger.debug(f"🚫 Слишком много ссылок ({len(urls_found)}) — пропущено")
            return False
        
        # Проверяем наличие ссылок на другие Telegram-каналы
        telegram_channel_pattern = r't\.me/[a-zA-Z0-9_]+|telegram\.me/[a-zA-Z0-9_]+'
        if re.search(telegram_channel_pattern, text, re.IGNORECASE):
            # Исключение: ссылка на наш квиз или официальный канал TERION — это нормально
            if not any(allowed in text.lower() for allowed in ["terion", "parkhomenko", "quiz"]):
                logger.debug("🚫 Ссылка на другой Telegram-канал — пропущено")
                return False
        
        # ── ФИЛЬТР 5: Фокус на запрос (вопросы или маркеры боли) ──────────────────
        # Проверяем наличие вопросительных знаков
        has_question_mark = "?" in text
        
        # Проверяем паттерны вопросов
        has_question_pattern = any(re.search(q, t_low) for q in self.QUESTION_PATTERNS)
        
        # Проверяем горячие триггеры (маркеры боли)
        has_hot_trigger = any(re.search(h, t_low) for h in self.HOT_TRIGGERS)
        
        # Если нет ни вопросов, ни горячих триггеров — пропускаем
        if not (has_question_mark or has_question_pattern or has_hot_trigger):
            logger.debug("🚫 Нет вопросов или маркеров боли — пропущено")
            return False
        
        # ── ФИЛЬТР 6: Проверка истории контактов (если есть author_id и БД) ───────
        # Примечание: Эта проверка выполняется в асинхронном контексте через _detect_lead_async
        # Здесь просто возвращаем True, если все остальные фильтры пройдены
        # Реальная проверка истории выполняется в _detect_lead_async перед вызовом detect_lead
        
        # ── ОСНОВНАЯ ЛОГИКА ДЕТЕКЦИИ ЛИДА ────────────────────────────────────────
        # Горячие триггеры — безусловный лид (уже проверили выше, но для ясности)
        if has_hot_trigger:
            return True
        
        # Проверка технических терминов
        has_tech = any(re.search(t, t_low) for t in self.TECHNICAL_TERMS)
        
        # Проверка коммерческих маркеров
        has_comm = any(re.search(c, t_low) for c in self.COMMERCIAL_MARKERS)
        
        # Для VK — более мягкая логика (ключевые слова достаточно)
        if platform == "vk":
            if has_tech:
                return True
        
        # Для Telegram — комбинация (тех.термин + вопрос ИЛИ тех.термин + коммерч.маркер)
        return has_tech and (has_question_mark or has_question_pattern or has_comm)

    async def parse_telegram(self, db=None) -> List[ScoutPost]:
        """
        Парсинг Telegram каналов с использованием Data-Driven Scout.
        Использует фильтрацию по платформе и приоритеты из БД.
        """
        from telethon import TelegramClient
        from config import API_ID, API_HASH
        
        posts = []
        client = TelegramClient('anton_parser', API_ID, API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            logger.error("❌ Антон не авторизован в Telegram!")
            await client.disconnect()
            return []

        # Загружаем цели из БД с фильтрацией по платформе (Data-Driven Scout)
        targets = await db.get_active_targets_for_scout(platform="telegram") if db else []
        
        if not targets:
            logger.warning("⚠️ Не найдено активных Telegram каналов в БД")
            await client.disconnect()
            return []
        
        logger.info(f"🔍 Сканирование {len(targets)} Telegram каналов...")
        
        # Сортируем по приоритету: сначала приоритетные ЖК (is_high_priority=1)
        targets_sorted = sorted(targets, key=lambda x: (x.get("is_high_priority", 0) == 0, x.get("title", "")))
        
        for target in targets_sorted:
            link = target.get("link")
            if not link: 
                continue
            
            # Используем geo_tag для заголовка карточки лида
            geo_tag = target.get("geo_tag", "")
            source_name = target.get("title", "Чат ЖК")
            if geo_tag:
                source_name = f"{geo_tag} | {source_name}"
            
            # Приоритетный ЖК - логируем отдельно
            is_priority = target.get("is_high_priority", 0) == 1
            if is_priority:
                logger.info(f"⭐ Приоритетный ЖК: {source_name}")
            
            try:
                # Используем last_post_id для инкрементального парсинга
                last_post_id = target.get("last_post_id", 0)
                limit = 100 if is_priority else 20  # Больше сообщений для приоритетных ЖК
                
                # Читаем сообщения с учетом last_post_id
                iter_params = {"limit": limit}
                if last_post_id > 0:
                    iter_params["min_id"] = last_post_id
                
                max_id = last_post_id
                for msg in client.iter_messages(link, **iter_params):
                    if msg.id > max_id:
                        max_id = msg.id
                    
                    if not msg.text:
                        continue
                    
                    # Определяем тип отправителя (канал или пользователь)
                    sender_type = None
                    author_id = None
                    author_name = None
                    
                    # В Telethon: если msg.post == True, это пост от имени канала
                    # Если msg.from_id есть, это сообщение от пользователя
                    if hasattr(msg, 'post') and msg.post:
                        sender_type = "channel"
                    elif hasattr(msg, 'from_id') and msg.from_id:
                        sender_type = "user"
                        author_id = msg.from_id.user_id if hasattr(msg.from_id, 'user_id') else None
                    elif hasattr(msg, 'sender_id'):
                        # Альтернативный способ определения отправителя
                        if hasattr(msg.sender_id, 'user_id'):
                            sender_type = "user"
                            author_id = msg.sender_id.user_id
                        elif hasattr(msg.sender_id, 'channel_id'):
                            sender_type = "channel"
                    
                    # Проверяем лид с учетом всех фильтров
                    if await self._detect_lead_async(
                        text=msg.text,
                        platform="telegram",
                        sender_type=sender_type,
                        author_id=author_id,
                        url=f"https://t.me/{link}/{msg.id}",
                        db=db
                    ):
                        # Получаем имя автора, если доступно
                        if hasattr(msg, 'sender') and msg.sender:
                            if hasattr(msg.sender, 'username'):
                                author_name = msg.sender.username
                            elif hasattr(msg.sender, 'first_name'):
                                author_name = msg.sender.first_name
                        
                        posts.append(ScoutPost(
                            source_type="telegram",
                            source_name=source_name,
                            source_id=str(msg.peer_id.channel_id if hasattr(msg.peer_id, 'channel_id') else msg.peer_id),
                            post_id=str(msg.id),
                            text=msg.text,
                            author_id=author_id,
                            author_name=author_name,
                            url=f"https://t.me/{link}/{msg.id}",
                            source_link=link  # Для использования geo_tag в hunter.py
                        ))
                
                # Обновляем last_post_id в БД
                if db and max_id > last_post_id:
                    try:
                        target_id = target.get("id")
                        if target_id:
                            await db.update_last_post_id(target_id, max_id)
                            logger.debug(f"✅ Обновлен last_post_id для {source_name}: {max_id}")
                    except Exception as e:
                        logger.warning(f"Не удалось обновить last_post_id для {source_name}: {e}")
                        
            except Exception as e:
                logger.error(f"⚠️ Ошибка парсинга {link}: {e}")
        
        await client.disconnect()
        logger.info(f"✅ Telegram: найдено {len(posts)} лидов из {len(targets)} каналов")
        
        # Сохраняем отчет сканирования
        self.last_scan_at = datetime.now()
        if not hasattr(self, 'last_scan_report'):
            self.last_scan_report = []
        
        return posts

    async def parse_vk(self, db=None) -> List[ScoutPost]:
        """
        Парсинг VK групп с использованием Data-Driven Scout.
        Использует фильтрацию по платформе и приоритеты из БД.
        """
        posts = []
        if not VK_TOKEN or "vk1.a" not in VK_TOKEN:
            logger.warning("⚠️ VK_TOKEN не настроен или невалиден")
            return []

        # Загружаем цели из БД с фильтрацией по платформе (Data-Driven Scout)
        targets = await db.get_active_targets_for_scout(platform="vk") if db else []
        
        if not targets:
            logger.warning("⚠️ Не найдено активных VK групп в БД")
            return []
        
        logger.info(f"🔍 Сканирование {len(targets)} VK групп...")
        
        # Сортируем по приоритету: сначала приоритетные ЖК
        targets_sorted = sorted(targets, key=lambda x: (x.get("is_high_priority", 0) == 0, x.get("title", "")))
        
        async with aiohttp.ClientSession() as session:
            for target in targets_sorted:
                link = target.get("link", "")
                if not link:
                    continue
                
                # Извлекаем ID группы из ссылки
                owner_id = str(link).replace("https://vk.com/public", "-").replace("https://vk.com/", "")
                # Если ID числовой и это группа, он должен начинаться с минус
                if owner_id.isdigit() and not owner_id.startswith("-"):
                    owner_id = f"-{owner_id}"
                
                # Используем geo_tag для заголовка карточки лида
                geo_tag = target.get("geo_tag", "")
                source_name = target.get("title", "Группа ВК")
                if geo_tag:
                    source_name = f"{geo_tag} | {source_name}"
                
                # Приоритетный ЖК - больше постов
                is_priority = target.get("is_high_priority", 0) == 1
                count = 100 if is_priority else 5  # Больше постов для приоритетных ЖК
                
                if is_priority:
                    logger.info(f"⭐ Приоритетный ЖК VK: {source_name}")

                url = f"https://api.vk.com/method/wall.get?owner_id={owner_id}&count={count}&access_token={VK_TOKEN}&v=5.131"
                try:
                    async with session.get(url) as resp:
                        data = await resp.json()
                        if "response" in data and "items" in data["response"]:
                            for item in data["response"]["items"]:
                                text = item.get("text", "")
                                if not text:
                                    continue
                                
                                # В VK определяем тип отправителя
                                sender_type = None
                                author_id = None
                                
                                # В VK посты от группы имеют from_id < 0, от пользователя > 0
                                from_id = item.get("from_id", 0)
                                if from_id < 0:
                                    sender_type = "channel"  # Пост от группы
                                elif from_id > 0:
                                    sender_type = "user"
                                    author_id = from_id
                                
                                # Проверяем лид с учетом всех фильтров
                                if await self._detect_lead_async(
                                    text=text,
                                    platform="vk",
                                    sender_type=sender_type,
                                    author_id=author_id,
                                    url=f"https://vk.com/wall{owner_id}_{item['id']}",
                                    db=db
                                ):
                                    # Получаем имя автора из VK API, если нужно
                                    author_name = None
                                    if author_id and author_id > 0:
                                        # Можно добавить запрос к VK API для получения имени
                                        # Пока оставляем None
                                        pass
                                    
                                    posts.append(ScoutPost(
                                        source_type="vk",
                                        source_name=source_name,
                                        source_id=owner_id,
                                        post_id=str(item["id"]),
                                        text=text,
                                        author_id=author_id,
                                        author_name=author_name,
                                        url=f"https://vk.com/wall{owner_id}_{item['id']}",
                                        source_link=link  # Для использования geo_tag в hunter.py
                                    ))
                except Exception as e:
                    logger.error(f"❌ Ошибка VK ({owner_id}): {e}")
        
        logger.info(f"✅ VK: найдено {len(posts)} лидов из {len(targets)} групп")
        
        # Сохраняем отчет сканирования
        self.last_scan_at = datetime.now()
        if not hasattr(self, 'last_scan_report'):
            self.last_scan_report = []
        
        return posts

    def extract_geo_header(self, text: str, source_name: str = "") -> str:
        """
        Гео-привязка: если в сообщении есть номер корпуса или название ЖК — вынести в заголовок карточки.
        Возвращает строку вида «ЖК Зиларт, корп. 5» или «ЖК Сердце Столицы» или source_name.
        """
        if not text:
            return source_name or ""
        t = text.strip()
        parts = []
        # Номер корпуса: корпус 5, корп. 3, корп 1, 2 корпус
        corp = re.search(r"(?:корпус|корп\.?)\s*[№#]?\s*(\d+[а-яa-z]?)", t, re.IGNORECASE)
        if corp:
            parts.append(f"корп. {corp.group(1)}")
        # Названия ЖК из нашего списка приоритетных
        for jk in self.PRIORITY_ZHK_NAMES:
            if jk in t.lower():
                if "сердце" in jk or jk == "сердце столицы":
                    parts.insert(0, "ЖК «Сердце Столицы»")
                elif jk == "символ":
                    parts.insert(0, "ЖК «Символ»")
                elif jk == "зиларт":
                    parts.insert(0, "ЖК «Зиларт»")
                elif "пресня" in jk or jk == "пресня сити":
                    parts.insert(0, "ЖК «Пресня Сити»")
                elif jk == "сити" or jk == "башн":
                    parts.insert(0, "Сити (Башни)")
                elif jk == "династия":
                    parts.insert(0, "ЖК «Династия»")
                break
        if not parts:
            return source_name or ""
        return ", ".join(parts)

    def get_last_scan_report(self):
        """
        Возвращает данные для формирования отчета в Телеграм.
        Использует информацию из БД о количестве активных ресурсов.
        """
        # Если есть отчет последнего скана, используем его
        if self.last_scan_report:
            tg_count = len([r for r in self.last_scan_report if r.get("type") == "telegram"])
            vk_count = len([r for r in self.last_scan_report if r.get("type") == "vk"])
            found_leads = sum(r.get("posts", 0) for r in self.last_scan_report)
            return {
                "tg_channels_count": tg_count,
                "vk_groups_count": vk_count,
                "found_leads": found_leads,
                "status": "Активен",
                "last_scan_at": self.last_scan_at.isoformat() if self.last_scan_at else None
            }
        
        # Базовая структура если отчета еще нет
        return {
            "tg_channels_count": 0,
            "vk_groups_count": 0,
            "found_leads": 0,
            "status": "Активен",
            "last_scan_at": None
        }

# КРИТИЧЕСКАЯ СТРОКА: Создаем объект, который ищет run_hunter.py
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
scout_parser = ScoutParser()
