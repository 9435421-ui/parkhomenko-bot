"""
Scout Parser — глобальный поиск лидов с гео-фильтрацией TERION.
"""
import pydantic
import sys

# Костыль для совместимости vkbottle 4.3.12 с pydantic v2
if pydantic.VERSION.startswith("2"):
    from pydantic import v1 as pydantic_v1
    sys.modules["pydantic.main"] = pydantic_v1.main

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
        client = TelegramClient('scanbot', API_ID, API_HASH)
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
                async for msg in client.iter_messages(link, **iter_params):
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
                                post_id = item.get("id")
                                text = item.get("text", "")
                                
                                # Парсим комментарии к посту, даже если в самом посте нет текста (может быть картинка с вопросом в комментах)
                                if post_id:
                                    comment_leads = await self.parse_vk_comments(owner_id, post_id, source_name, link, db=db)
                                    posts.extend(comment_leads)

                                if not text:
                                    logger.debug("Пропущен пост без текста")
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
                    # Парсим обсуждения группы
                    board_leads = await self.parse_vk_board(owner_id, source_name, link, db=db)
                    posts.extend(board_leads)

                except Exception as e:
                    logger.error(f"❌ Ошибка VK ({owner_id}): {e}")
        
        logger.info(f"✅ VK: найдено {len(posts)} лидов из {len(targets)} групп")
        
        # Сохраняем отчет сканирования
        self.last_scan_at = datetime.now()
        if not hasattr(self, 'last_scan_report'):
            self.last_scan_report = []
        
        return posts

    async def parse_vk_comments(self, owner_id: str, post_id: str, source_name: str, link: str, db=None) -> List[ScoutPost]:
        """Парсинг комментариев к посту ВК"""
        posts = []
        url = f"https://api.vk.com/method/wall.getComments?owner_id={owner_id}&post_id={post_id}&count=100&need_likes=1&access_token={VK_TOKEN}&v=5.131"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = await resp.json()
                    if "response" in data and "items" in data["response"]:
                        for item in data["response"]["items"]:
                            text = item.get("text", "")
                            if not text:
                                continue
                            
                            from_id = item.get("from_id", 0)
                            if from_id == 0: continue
                            
                            author_id = from_id if from_id > 0 else None
                            sender_type = "user" if from_id > 0 else "channel"
                            
                            if await self._detect_lead_async(
                                text=text,
                                platform="vk",
                                sender_type=sender_type,
                                author_id=author_id,
                                url=f"https://vk.com/wall{owner_id}_{post_id}?reply={item['id']}",
                                db=db
                            ):
                                posts.append(ScoutPost(
                                    source_type="vk",
                                    source_name=f"{source_name} (коммент)",
                                    source_id=owner_id,
                                    post_id=f"{post_id}_{item['id']}",
                                    text=text,
                                    author_id=author_id,
                                    url=f"https://vk.com/wall{owner_id}_{post_id}?reply={item['id']}",
                                    is_comment=True,
                                    source_link=link
                                ))
        except Exception as e:
            logger.error(f"❌ Ошибка VK comments ({owner_id}_{post_id}): {e}")
        return posts

    async def parse_vk_board(self, group_id: str, source_name: str, link: str, db=None) -> List[ScoutPost]:
        """Парсинг обсуждений (board) ВК"""
        posts = []
        # Сначала получаем список тем
        group_id_abs = group_id.lstrip("-")
        url_topics = f"https://api.vk.com/method/board.getTopics?group_id={group_id_abs}&count=10&order=1&access_token={VK_TOKEN}&v=5.131"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url_topics) as resp:
                    data = await resp.json()
                    if "response" in data and "items" in data["response"]:
                        for topic in data["response"]["items"]:
                            topic_id = topic["id"]
                            # Получаем сообщения в теме
                            url_msgs = f"https://api.vk.com/method/board.getComments?group_id={group_id_abs}&topic_id={topic_id}&count=50&sort=desc&access_token={VK_TOKEN}&v=5.131"
                            async with session.get(url_msgs) as resp_msgs:
                                data_msgs = await resp_msgs.json()
                                if "response" in data_msgs and "items" in data_msgs["response"]:
                                    for item in data_msgs["response"]["items"]:
                                        text = item.get("text", "")
                                        if not text: continue
                                        
                                        from_id = item.get("from_id", 0)
                                        if from_id <= 0: continue # Только от пользователей
                                        
                                        if await self._detect_lead_async(
                                            text=text,
                                            platform="vk",
                                            sender_type="user",
                                            author_id=from_id,
                                            url=f"https://vk.com/topic-{group_id_abs}_{topic_id}?post={item['id']}",
                                            db=db
                                        ):
                                            posts.append(ScoutPost(
                                                source_type="vk",
                                                source_name=f"{source_name} (обсуждение)",
                                                source_id=f"-{group_id_abs}",
                                                post_id=f"topic_{topic_id}_{item['id']}",
                                                text=text,
                                                author_id=from_id,
                                                url=f"https://vk.com/topic-{group_id_abs}_{topic_id}?post={item['id']}",
                                                is_comment=True,
                                                source_link=link
                                            ))
        except Exception as e:
            logger.error(f"❌ Ошибка VK board ({group_id}): {e}")
        return posts

    async def search_vk_global(self, db=None, hours_back: int = 24) -> List[ScoutPost]:
        """
        Глобальный поиск по всему ВКонтакте через newsfeed.search.
        Ищет посты по ключевым словам, фильтрует по времени (по умолчанию 24 часа),
        автоматически добавляет активные сообщества в БД.
        
        Args:
            db: Database instance
            hours_back: Сколько часов назад искать записи (по умолчанию 24)
        
        Returns:
            List[ScoutPost]: Найденные лиды
        """
        posts = []
        if not VK_TOKEN or "vk1.a" not in VK_TOKEN:
            logger.warning("⚠️ VK_TOKEN не настроен или невалиден")
            return []
        
        # Проверка формата токена (должен начинаться с буквы или цифры)
        if VK_TOKEN and len(VK_TOKEN) > 0:
            first_char = VK_TOKEN[0]
            if not (first_char.isalnum()):
                logger.error("❌ Ошибка формата VK_TOKEN в .env")
                return []
        
        # Ключевые слова для поиска
        search_queries = [
            "перепланировка",
            "согласование МЖИ",
            "узаконить перепланировку",
            "нежилое помещение",
            "изменение назначения",
            "коммерция в ЖК",
            "предписание МЖИ",
            "штраф за перепланировку"
        ]
        
        # Рассчитываем timestamp для фильтра по времени
        start_time = int((datetime.now() - timedelta(hours=hours_back)).timestamp())
        
        # Множество для отслеживания найденных групп (чтобы не добавлять дубликаты)
        discovered_groups = set()
        
        logger.info("🚀 Начинаю глобальный поиск в ВК...")
        logger.info(f"🌍 Запуск глобального поиска VK за последние {hours_back} часов...")
        
        async with aiohttp.ClientSession() as session:
            for query in search_queries:
                logger.info(f"🔍 Поиск по запросу: '{query}'")
                
                # VK API newsfeed.search
                # count=200 максимум, extended=1 для получения информации о группах
                url = (
                    f"https://api.vk.com/method/newsfeed.search"
                    f"?q={query}"
                    f"&count=200"
                    f"&extended=1"
                    f"&start_time={start_time}"
                    f"&fields=members_count,activity,description"
                    f"&access_token={VK_TOKEN}"
                    f"&v=5.131"
                )
                
                try:
                    async with session.get(url) as resp:
                        data = await resp.json()
                        
                        if "error" in data:
                            error_msg = data["error"].get("error_msg", "Unknown error")
                            logger.error(f"❌ VK API error: {error_msg}")
                            continue
                        
                        if "response" not in data:
                            continue
                        
                        response = data["response"]
                        items = response.get("items", [])
                        profiles = {p["id"]: p for p in response.get("profiles", [])}
                        groups = {g["id"]: g for g in response.get("groups", [])}
                        
                        logger.info(f"   Найдено записей: {len(items)}")
                        
                        for item in items:
                            text = item.get("text", "")
                            if not text:
                                logger.debug("Пропущен пост без текста")
                                continue
                            
                            # Получаем ID источника
                            owner_id = item.get("owner_id", 0)
                            post_id = item.get("id", 0)
                            
                            # Определяем тип источника (группа или пользователь)
                            if owner_id < 0:
                                # Это группа
                                group_id = abs(owner_id)
                                group_info = groups.get(group_id, {})
                                source_name = group_info.get("name", f"club{group_id}")
                                source_link = f"https://vk.com/club{group_id}"
                                members_count = group_info.get("members_count", 0)
                                
                                # Добавляем группу в discovered для последующего сохранения в БД
                                discovered_groups.add((
                                    group_id,
                                    source_name,
                                    source_link,
                                    members_count,
                                    group_info.get("activity", ""),
                                    group_info.get("description", "")
                                ))
                                
                                sender_type = "channel"
                                author_id = None
                            else:
                                # Это пользователь
                                user_info = profiles.get(owner_id, {})
                                first_name = user_info.get("first_name", "")
                                last_name = user_info.get("last_name", "")
                                source_name = f"{first_name} {last_name}".strip() or f"id{owner_id}"
                                source_link = f"https://vk.com/id{owner_id}"
                                sender_type = "user"
                                author_id = owner_id
                            
                            # URL поста
                            post_url = f"https://vk.com/wall{owner_id}_{post_id}"
                            
                            # Дата публикации
                            date_ts = item.get("date", 0)
                            published_at = datetime.fromtimestamp(date_ts) if date_ts else None
                            
                            # Проверяем является ли пост лидом
                            if await self._detect_lead_async(
                                text=text,
                                platform="vk",
                                sender_type=sender_type,
                                author_id=author_id,
                                url=post_url,
                                db=db
                            ):
                                posts.append(ScoutPost(
                                    source_type="vk",
                                    source_name=source_name,
                                    source_id=str(owner_id),
                                    post_id=str(post_id),
                                    text=text,
                                    author_id=author_id,
                                    author_name=source_name if sender_type == "user" else None,
                                    url=post_url,
                                    published_at=published_at,
                                    source_link=source_link
                                ))
                                
                except Exception as e:
                    logger.error(f"❌ Ошибка при поиске '{query}': {e}")
                
                # Небольшая задержка между запросами чтобы не превысить лимиты VK API
                await asyncio.sleep(0.5)
        
        # Автоматическое добавление найденных групп в БД
        if db and discovered_groups:
            logger.info(f"📊 Найдено {len(discovered_groups)} уникальных сообществ, добавляем в БД...")
            added_count = 0
            skipped_count = 0
            
            for group_id, name, link, members, activity, description in discovered_groups:
                try:
                    # Проверяем есть ли уже в БД
                    existing = await db.get_target_resource_by_link(link)
                    
                    if not existing:
                        # Добавляем новое сообщество
                        await db.add_target_resource(
                            resource_type="vk",
                            link=link,
                            title=name,
                            notes=f"Найдено через newsfeed.search | Активность: {activity} | Участников: {members} | {description[:100] if description else ''}",
                            status="active",
                            participants_count=members,
                            geo_tag=""  # Будет определено позже через set_geo
                        )
                        added_count += 1
                        logger.info(f"   ➕ Добавлено: {name} ({members} участников)")
                    else:
                        skipped_count += 1
                        
                except Exception as e:
                    logger.warning(f"   ⚠️ Ошибка добавления {link}: {e}")
            
            logger.info(f"✅ Добавлено {added_count} новых, пропущено {skipped_count} существующих")
        
        logger.info(f"🎯 Глобальный поиск VK завершен: найдено {len(posts)} лидов")
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

    def get_last_scan_report(self) -> str:
        """
        Возвращает отформатированный отчет в виде строки для Telegram.
        """
        if self.last_scan_report:
            tg_ok = [r for r in self.last_scan_report if r.get("type") == "telegram"]
            vk_ok = [r for r in self.last_scan_report if r.get("type") == "vk"]
            found = sum(r.get("posts", 0) for r in self.last_scan_report)
            scan_time = self.last_scan_at.strftime('%d.%m.%Y %H:%M') if self.last_scan_at else "—"
            return (
                f"🕵️ <b>Отчёт шпиона</b>\n\n"
                f"📱 Telegram каналов: {len(tg_ok)}\n"
                f"📘 VK групп: {len(vk_ok)}\n"
                f"🎯 Найдено лидов: {found}\n"
                f"🕐 Время скана: {scan_time}"
            )
        return "Отчёта ещё нет — шпион ещё не запускался"

# КРИТИЧЕСКАЯ СТРОКА: Создаем объект, который ищет run_hunter.py
scout_parser = ScoutParser()
