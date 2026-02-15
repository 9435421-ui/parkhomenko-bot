"""
Scout Parser — агент для парсинга Telegram каналов и VK групп.

Функционал:
1. Telegram: Парсинг каналов Химок, Красногорска, Севера/СЗ Москвы
2. VK: Парсинг групп, поиск по ключевым словам, комментарии и личные сообщения

Каналы для мониторинга:
- Химки, Красногорск, Север/СЗ Москвы

Ключевые слова:
- "перепланировка", "согласование", "узаконить"

VK группы:
- "Химки Бесплатка"
- "Красногорск Барахолка"
- "Москва Перепланировка"
"""
import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

import aiohttp

from config import VK_TOKEN, VK_GROUP_ID

logger = logging.getLogger(__name__)


@dataclass
class ScoutPost:
    """Пост из канала/группы"""
    source_type: str  # "telegram" или "vk"
    source_name: str
    source_id: str
    post_id: str
    text: str
    author_id: Optional[int] = None
    author_name: Optional[str] = None
    url: str = ""
    published_at: Optional[datetime] = None
    likes: int = 0
    comments: int = 0


class ScoutParser:
    """
    Scout Agent для парсинга Telegram каналов и VK групп.
    
    Ищет посты по ключевым словам и оставляет комментарии с предложением помощи.
    """

    # === TELEGRAM КАНАЛЫ (Москва и МО: жилая + коммерция + дизайн/строй) ===
    TG_CHANNELS = [
        {"id": "novostroyman", "name": "Новостройки Москвы и МО", "geo": "Москва/МО"},
        {"id": "NovostroyM", "name": "Первичка Московский регион", "geo": "Москва/МО"},
        {"id": "nedvigimost_moskva", "name": "Недвижимость Москва", "geo": "Москва/МО"},
        {"id": "domostroy_channel", "name": "Строительство и недвижимость", "geo": "Москва/МО"},
        {"id": "belaya_kaska", "name": "Белая каска недвижимость", "geo": "Москва/МО"},
        {"id": "THEMOSCOWCITY", "name": "Москва-Сити", "geo": "Москва"},
        {"id": "startyprodazh", "name": "Старты продаж", "geo": "Москва/МО"},
        # Коммерческая недвижимость, брокеры, стрит-ритейл
        {"id": "nmarketpro_commerce", "name": "Нмаркет.ПРО коммерция", "geo": "Москва/МО"},
        {"id": "mallsru", "name": "Malls.ru торговля и недвижимость", "geo": "Москва/МО"},
        {"id": "arendmoscow", "name": "Аренда Москва (офисы, помещения)", "geo": "Москва/МО"},
        # Дизайн и ремонт (согласованиями часто не занимаются)
        {"id": "decor_journal", "name": "Дизайн и ремонт | Интерьер", "geo": "Москва/МО"},
        {"id": "avenco", "name": "АВЕНКО дизайн и ремонт Москва", "geo": "Москва/МО"},
        {"id": "ukvartira", "name": "Уютная квартира | дизайн", "geo": "Москва/МО"},
        # DIY и ремонт — «народные» чаты
        {"id": "idea_remont", "name": "Идеи для ремонта", "geo": "Москва/МО"},
        {"id": "remont_sovet", "name": "Советы по ремонту", "geo": "Москва/МО"},
        {"id": "design_kvartiry", "name": "Дизайн и отделка", "geo": "Москва/МО"},
        {"id": "kvartira_vopros", "name": "Вопросы жильцов", "geo": "Москва/МО"},
    ]

    # === VK ГРУППЫ (ID групп, Москва и МО) ===
    VK_GROUPS = [
        {"id": "133756068", "name": "Ремонт квартир Москва и Подмосковье", "geo": "Москва/МО"},
        {"id": "124518536", "name": "Недвижимость услуги", "geo": "Москва/МО"},
        {"id": "152491538", "name": "Реновация Москва (обсуждения)", "geo": "Москва"},
        {"id": "235569022", "name": "ТЕРИОН / перепланировки", "geo": "Москва/МО"},
        {"id": "29534144", "name": "Москва 24", "geo": "Москва"},
    ]

    # === КЛЮЧЕВЫЕ СЛОВА ===
    KEYWORDS = [
        "перепланировка",
        "согласование",
        "узаконить",
        "перепланировку",
        "согласовать",
        "проект перепланировки",
        "МЖИ",
        "перепланировки",
        "нежилое помещение",
        "коммерция",
        "антресоль",
        "отдельный вход",
        "общепит",
        "кафе",
        "офис",
        "изменение назначения",
        # DIY и ремонт
        "своими руками",
        "сломали стену",
        "перенесли радиатор",
        "залили пол",
        "хотим объединить",
    ]

    # === ТРИГГЕРНЫЕ ФРАЗЫ ДЛЯ ПОИСКА ЛИДОВ ===
    LEAD_TRIGGERS = [
        r"перепланиров",
        r"согласовани",
        r"узакони",
        r"проект",
        r"план\s+(квартир|комнат| помещен)",
        r"снос\s+стен",
        r"объединение\s+(кухни|комнат|ванной)",
        r"ремонт\s+(в|своей)\s+квартир",
        r"нежилое\s+помещен",
        r"коммерц",
        r"антресол",
        r"отдельный\s+вход",
        r"общепит",
        r"изменение\s+назначен",
        r"офис",
        r"кафе",
        # DIY и «народные» формулировки
        r"своими\s+руками",
        r"сломали\s+стену",
        r"перенесли\s+радиатор",
        r"залили\s+пол",
        r"хотим\s+объединить",
    ]

    def __init__(self):
        self.vk_token = VK_TOKEN
        self.vk_api_version = "5.199"
        
        # Telegram credentials
        self.telegram_api_id = os.getenv("TELEGRAM_API_ID", "")
        self.telegram_api_hash = os.getenv("TELEGRAM_API_HASH", "")
        self.telegram_phone = os.getenv("TELEGRAM_PHONE", "")
        
        # Настройки
        from config import SCOUT_ENABLED, SCOUT_TG_CHANNELS, SCOUT_VK_GROUPS, SCOUT_TG_KEYWORDS, SCOUT_VK_KEYWORDS
        self.enabled = SCOUT_ENABLED
        self.check_interval = int(os.getenv("SCOUT_PARSER_INTERVAL", "1800"))  # 30 минут

        # Каналы и группы: сначала детальный .env (SCOUT_TG_CHANNEL_1_ID и т.д.), иначе список из .env, иначе дефолт (Москва/МО)
        self.tg_channels = self._load_tg_channels()
        if not self.tg_channels and SCOUT_TG_CHANNELS:
            self.tg_channels = [{"id": c.strip(), "name": c.strip(), "geo": "Москва/МО"} for c in SCOUT_TG_CHANNELS if c and c.strip()]
        if not self.tg_channels:
            self.tg_channels = self.TG_CHANNELS

        self.vk_groups = self._load_vk_groups()
        if not self.vk_groups and SCOUT_VK_GROUPS:
            self.vk_groups = [{"id": g.strip(), "name": g.strip(), "geo": "Москва/МО"} for g in SCOUT_VK_GROUPS if g and g.strip()]
        if not self.vk_groups:
            self.vk_groups = self.VK_GROUPS

        # Отчёт последнего скана: где был шпион, куда удалось попасть
        self.last_scan_report = []  # list of {"type", "name", "id", "status": "ok"|"error", "posts": N, "error": str|None}
        self.last_scan_at: Optional[datetime] = None

        logger.info(f"🔍 ScoutParser инициализирован. Включен: {'✅' if self.enabled else '❌'}. TG каналов: {len(self.tg_channels)}, VK групп: {len(self.vk_groups)}")

    def _load_tg_channels(self) -> List[Dict]:
        """Загрузка TG каналов из .env"""
        channels = []
        for i in range(1, 11):
            channel_id = os.getenv(f"SCOUT_TG_CHANNEL_{i}_ID", "")
            channel_name = os.getenv(f"SCOUT_TG_CHANNEL_{i}_NAME", "")
            channel_geo = os.getenv(f"SCOUT_TG_CHANNEL_{i}_GEO", "")
            if channel_id and channel_name:
                channels.append({"id": channel_id, "name": channel_name, "geo": channel_geo or "Москва/МО"})
        
        # Дефолтные каналы если не настроены
        if not channels:
            channels = self.TG_CHANNELS
        
        return channels

    def _load_vk_groups(self) -> List[Dict]:
        """Загрузка VK групп из .env"""
        groups = []
        for i in range(1, 11):
            group_id = os.getenv(f"SCOUT_VK_GROUP_{i}_ID", "")
            group_name = os.getenv(f"SCOUT_VK_GROUP_{i}_NAME", "")
            group_geo = os.getenv(f"SCOUT_VK_GROUP_{i}_GEO", "")
            if group_id and group_name:
                groups.append({"id": group_id, "name": group_name, "geo": group_geo or "Москва/МО"})
        
        # Дефолтные группы если не настроены
        if not groups:
            groups = self.VK_GROUPS
        
        return groups

    def _load_keywords(self) -> List[str]:
        """Загрузка ключевых слов из .env"""
        keywords_str = os.getenv("SCOUT_KEYWORDS", "")
        if keywords_str:
            return [k.strip() for k in keywords_str.split(",") if k.strip()]
        return self.KEYWORDS

    def detect_lead(self, text: str) -> bool:
        """Проверка, содержит ли текст триггерную фразу"""
        text_lower = text.lower()
        for trigger in self.LEAD_TRIGGERS:
            if re.search(trigger, text_lower):
                return True
        # Также проверяем ключевые слова
        keywords = self._load_keywords()
        for keyword in keywords:
            if keyword.lower() in text_lower:
                return True
        return False

    def generate_outreach_message(self, source_type: str = "telegram", geo: str = "") -> str:
        """Генерация сообщения для комментария/ответа"""
        if source_type == "telegram":
            return (
                "Привет! 👋 Видим, что вы ищете помощь с перепланировкой. \n"
                "Мы специализируемся на согласовании в Химках/Красногорске/Москве. \n"
                "Бесплатная консультация: @Parkhovenko_i_kompaniya_bot"
            )
        else:
            return (
                "Добрый день! 👋 Помогаем с согласованием перепланировок в вашем районе. \n"
                "Узаконим даже сложные случаи. \n"
                "Пишите в ЛС или бот: @Parkhovenko_i_kompaniya_bot"
            )

    def _tg_post_url(self, channel_id, message_id: int) -> str:
        """Ссылка на пост: для username — t.me/username/msg, для -100XXX — t.me/c/num/msg."""
        sid = str(channel_id)
        if sid.startswith("-100"):
            return f"https://t.me/c/{sid.replace('-100', '')}/{message_id}"
        return f"https://t.me/{channel_id}/{message_id}"

    # === TELEGRAM PARSING ===

    async def parse_telegram(self) -> List[ScoutPost]:
        from telethon import TelegramClient
        from config import API_ID, API_HASH

        posts = []
        client = TelegramClient('anton_parser', API_ID, API_HASH)

        await client.connect()
        if not await client.is_user_authorized():
            logger.error("❌ Антон не авторизован в Telegram!")
            return []

        # Лимит постов на канал (раньше 15 — мало; люди спрашивают в чатах, не в каналах)
        tg_limit = int(os.getenv("SCOUT_TG_MESSAGES_LIMIT", "50"))

        for channel in self.tg_channels:
            count = 0
            scanned = 0
            try:
                async for message in client.iter_messages(channel['id'], limit=tg_limit):
                    if not message.text:
                        continue
                    scanned += 1
                    if self.detect_lead(message.text):
                        post = ScoutPost(
                            source_type="telegram",
                            source_name=channel['name'],
                            source_id=str(channel['id']),
                            post_id=str(message.id),
                            text=message.text,
                            url=self._tg_post_url(channel['id'], message.id),
                        )
                        posts.append(post)
                        count += 1
                self.last_scan_report.append({
                    "type": "telegram",
                    "name": channel["name"],
                    "id": channel["id"],
                    "status": "ok",
                    "posts": count,
                    "scanned": scanned,
                    "error": None,
                })
            except Exception as e:
                logger.error(f"❌ Ошибка парсинга ТГ {channel['name']}: {e}")
                self.last_scan_report.append({
                    "type": "telegram",
                    "name": channel["name"],
                    "id": channel["id"],
                    "status": "error",
                    "posts": 0,
                    "scanned": 0,
                    "error": str(e)[:200],
                })

        await client.disconnect()
        return posts

    async def _send_telegram_comment(self, channel_id: str, message_id: int, text: str):
        """Отправка комментария в Telegram канал"""
        # TODO: Реализовать через Telethon
        logger.info(f"💬 TG комментарий: {text[:50]}...")
        pass

    # === VK PARSING ===

    async def _vk_request(self, method: str, params: dict) -> Optional[dict]:
        """Выполнение запроса к VK API"""
        if not self.vk_token:
            logger.error("❌ VK_TOKEN не настроен")
            return None
        
        params["access_token"] = self.vk_token
        params["v"] = self.vk_api_version
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.vk.com/method/{method}",
                    params=params
                ) as resp:
                    data = await resp.json()
                    if "error" in data:
                        logger.error(f"❌ VK API error: {data['error']}")
                        return None
                    return data.get("response")
        except Exception as e:
            logger.error(f"❌ VK request error: {e}")
            return None

    async def parse_vk(self) -> List[ScoutPost]:
        """
        Парсинг VK групп.
        
        Ищет посты по ключевым словам, оставляет комментарии.
        """
        if not self.enabled:
            logger.info("🔍 Scout VK: выключен")
            return []
        
        if not self.vk_token:
            logger.error("❌ VK_TOKEN не настроен")
            return []
        
        logger.info(f"🔍 Сканирование {len(self.vk_groups)} VK групп...")

        posts = []
        keywords = self._load_keywords()

        # Сколько постов брать для разбора комментариев (в комментариях чаще пишут «посоветуйте», «как узаконить»)
        vk_posts_to_scan = int(os.getenv("SCOUT_VK_POSTS_FOR_COMMENTS", "10"))
        vk_comments_per_post = int(os.getenv("SCOUT_VK_COMMENTS_PER_POST", "30"))

        for group in self.vk_groups:
            count = 0
            scanned_wall = 0
            scanned_comments = 0
            try:
                wall_posts = await self._vk_request("wall.get", {
                    "owner_id": -int(group["id"]),
                    "count": 50,
                    "extended": 0
                })

                if not wall_posts or "items" not in wall_posts:
                    self.last_scan_report.append({
                        "type": "vk",
                        "name": group["name"],
                        "id": group["id"],
                        "status": "ok",
                        "posts": 0,
                        "scanned": 0,
                        "error": None,
                    })
                    continue

                items = wall_posts["items"]
                scanned_wall = len(items)

                # Посты на стене
                for item in items:
                    text = item.get("text", "")
                    if self.detect_lead(text):
                        post = ScoutPost(
                            source_type="vk",
                            source_name=group["name"],
                            source_id=group["id"],
                            post_id=str(item["id"]),
                            text=text,
                            author_id=item.get("from_id"),
                            url=f"https://vk.com/wall-{group['id']}_{item['id']}",
                            published_at=datetime.fromtimestamp(item.get("date", 0)),
                            likes=item.get("likes", {}).get("count", 0),
                            comments=item.get("comments", {}).get("count", 0),
                        )
                        posts.append(post)
                        count += 1
                        await self.send_vk_comment(
                            item["id"], group["id"],
                            self.generate_outreach_message("vk", group["geo"])
                        )
                        if item.get("from_id"):
                            await self.send_vk_message(
                                item["from_id"],
                                self.generate_outreach_message("vk", group["geo"])
                            )

                # Комментарии к постам — там чаще пишут люди «посоветуйте мастера», «как узаконить»
                for item in items[:vk_posts_to_scan]:
                    comments_data = await self._vk_request("wall.getComments", {
                        "owner_id": -int(group["id"]),
                        "post_id": item["id"],
                        "count": vk_comments_per_post,
                        "need_likes": 0,
                        "extended": 0,
                    })
                    if not comments_data or "items" not in comments_data:
                        continue
                    for comm in comments_data.get("items", []):
                        scanned_comments += 1
                        ctext = comm.get("text", "")
                        if not ctext or not self.detect_lead(ctext):
                            continue
                        post = ScoutPost(
                            source_type="vk",
                            source_name=group["name"] + " (коммент)",
                            source_id=group["id"],
                            post_id=f"{item['id']}_c{comm.get('id', 0)}",
                            text=ctext,
                            author_id=comm.get("from_id"),
                            url=f"https://vk.com/wall-{group['id']}_{item['id']}?reply={comm.get('id', 0)}",
                            published_at=datetime.fromtimestamp(comm.get("date", 0)) if comm.get("date") else None,
                            likes=0,
                            comments=0,
                        )
                        posts.append(post)
                        count += 1
                        if comm.get("from_id"):
                            await self.send_vk_message(
                                comm["from_id"],
                                self.generate_outreach_message("vk", group["geo"])
                            )

                self.last_scan_report.append({
                    "type": "vk",
                    "name": group["name"],
                    "id": group["id"],
                    "status": "ok",
                    "posts": count,
                    "scanned": scanned_wall + scanned_comments,
                    "error": None,
                })
            except Exception as e:
                logger.error(f"❌ Ошибка группы {group['name']}: {e}")
                self.last_scan_report.append({
                    "type": "vk",
                    "name": group["name"],
                    "id": group["id"],
                    "status": "error",
                    "posts": 0,
                    "scanned": 0,
                    "error": str(e)[:200],
                })
        
        logger.info(f"🔍 VK: найдено {len(posts)} постов с лидами")
        return posts

    async def send_vk_comment(self, post_id: int, group_id: str, message: str) -> bool:
        """
        Отправка комментария под постом ВК.
        
        Args:
            post_id: ID поста
            group_id: ID группы (отрицательное число)
            message: Текст комментария
        
        Returns:
            True если успешно
        """
        try:
            result = await self._vk_request("wall.createComment", {
                "owner_id": -int(group_id),
                "post_id": post_id,
                "message": message,
                "from_group": VK_GROUP_ID  # От имени группы
            })
            
            if result:
                logger.info(f"💬 VK комментарий к посту {post_id}: {message[:50]}...")
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка VK комментария: {e}")
            return False

    async def send_vk_message(self, user_id: int, message: str) -> bool:
        """
        Отправка личного сообщения в ВК.
        
        Args:
            user_id: ID пользователя
            message: Текст сообщения
        
        Returns:
            True если успешно
        """
        try:
            # Проверяем, открыты ли личные сообщения
            settings = await self._vk_request("account.getInfo", {})
            
            result = await self._vk_request("messages.send", {
                "user_id": user_id,
                "message": message,
                "random_id": int(datetime.now().timestamp() * 1000)
            })
            
            if result:
                logger.info(f"💬 VK сообщение пользователю {user_id}: {message[:50]}...")
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка VK сообщения: {e}")
            return False

    # === FULL SCAN ===

    async def scan_all(self) -> List[ScoutPost]:
        """Полное сканирование всех источников. Заполняет last_scan_report."""
        self.last_scan_report = []
        self.last_scan_at = datetime.now()
        all_posts = []

        try:
            tg_posts = await self.parse_telegram()
            all_posts.extend(tg_posts)
        except Exception as e:
            logger.error(f"❌ TG scan error: {e}")

        try:
            vk_posts = await self.parse_vk()
            all_posts.extend(vk_posts)
        except Exception as e:
            logger.error(f"❌ VK scan error: {e}")

        return all_posts

    def get_last_scan_report(self) -> str:
        """Форматированный отчёт: где был шпион, сколько просмотрено, сколько лидов."""
        if not self.last_scan_report:
            return "📭 Отчёта ещё нет. Дождитесь следующего запуска охоты за лидами (раз в 2 часа)."
        lines = ["🕵️ <b>Где был шпион</b> (последний скан)"]
        if self.last_scan_at:
            lines.append(f"⏱ {self.last_scan_at.strftime('%d.%m.%Y %H:%M')}\n")
        tg_ok = [r for r in self.last_scan_report if r["type"] == "telegram" and r["status"] == "ok"]
        tg_err = [r for r in self.last_scan_report if r["type"] == "telegram" and r["status"] == "error"]
        vk_ok = [r for r in self.last_scan_report if r["type"] == "vk" and r["status"] == "ok"]
        vk_err = [r for r in self.last_scan_report if r["type"] == "vk" and r["status"] == "error"]
        total_scanned = sum(r.get("scanned", 0) for r in tg_ok + vk_ok)
        total_leads = sum(r.get("posts", 0) for r in tg_ok + vk_ok)
        lines.append(f"📊 Просмотрено сообщений/постов: <b>{total_scanned}</b>, с ключевыми словами: <b>{total_leads}</b>\n")
        if tg_ok or tg_err:
            lines.append("<b>📱 Telegram каналы:</b>")
            for r in tg_ok:
                s = f"  ✅ {r['name']} — {r['posts']} лидов"
                if r.get("scanned") is not None:
                    s += f" (просмотрено {r['scanned']})"
                lines.append(s)
            for r in tg_err:
                lines.append(f"  ❌ {r['name']} — {r.get('error', 'ошибка')}")
        if vk_ok or vk_err:
            lines.append("<b>📘 VK группы:</b>")
            for r in vk_ok:
                s = f"  ✅ {r['name']} — {r['posts']} лидов"
                if r.get("scanned") is not None:
                    s += f" (просмотрено {r['scanned']})"
                lines.append(s)
            for r in vk_err:
                lines.append(f"  ❌ {r['name']} — {r.get('error', 'ошибка')}")
        if total_scanned > 0 and total_leads == 0:
            lines.append("\n💡 Если лидов 0 при большом объёме — см. docs/SCOUT_WHY_NO_LEADS.md")
        return "\n".join(lines)


# Экземпляр парсера
scout_parser = ScoutParser()


async def run_scout_parser():
    """Запуск Scout Parser в бесконечном цикле"""
    if not scout_parser.enabled:
        logger.info("🔍 Scout Parser: выключен")
        return
    
    logger.info("🔍 Scout Parser запущен")
    
    while True:
        try:
            posts = await scout_parser.scan_all()
            if posts:
                logger.info(f"🔍 Найдено {len(posts)} лидов")
        except Exception as e:
            logger.error(f"❌ Scout error: {e}")
        
        await asyncio.sleep(scout_parser.check_interval)
