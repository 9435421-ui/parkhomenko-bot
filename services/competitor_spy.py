<<<<<<< HEAD
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class CompetitorSpy:
    def __init__(self):
        self.geo_monitoring_enabled = False
        logger.info("CompetitorSpy инициализирован (заглушка)")

    async def scan_geo_chats(self) -> List[Dict]:
        """Сканирование гео-чатов (заглушка)"""
        return []

competitor_spy = CompetitorSpy()
=======
"""
Competitor Spy / Hunter Service — агент для мониторинга каналов конкурентов.

Функционал:
1. Слежка: Мониторит заданные каналы конкурентов по перепланировкам и строительству
2. GEO-мониторинг: Отслеживает чаты ЖК Москвы и Подмосковья
3. Анализ: Выделяет самые «горячие» темы, которые набрали больше всего реакций
4. Alerts: Отправляет уведомления менеджеру о найденных лидах в целевых чатах
"""
import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class CompetitorPost:
    """Пост конкурента"""
    channel_name: str
    channel_id: str
    text: str
    views: int
    likes: int
    comments: int
    forwards: int
    url: str
    published_at: datetime
    engagement_score: float = 0.0


@dataclass
class TrendingTopic:
    """Горячая тема"""
    topic: str
    source_channels: List[str]
    total_engagement: int
    post_examples: List[CompetitorPost]
    recommendations: str = ""


@dataclass
class LocalLead:
    """Локальный лид из чата ЖК"""
    chat_name: str
    chat_id: str
    user_name: str
    user_id: int
    message: str
    message_url: str
    detected_intent: str
    geo_context: str
    timestamp: datetime


class CompetitorSpy:
    """
    Агент-шпион/охотник для мониторинга конкурентов и чатов ЖК.
    
    Мониторит каналы конкурентов и чаты ЖК, передаёт горячие темы Креативщику.
    """

    # === ГЕО-КОНФИГУРАЦИЯ ===
    
    # TARGET_GEO_CHATS — чаты ЖК Москвы (для ТЕРИОН)
    TARGET_GEO_CHATS = [
        {"id": "@perekrestok_moscow", "name": "ЖК Перекресток", "geo": "Москва, ЦАО"},
        {"id": "@samolet_msk", "name": "Группа Самолет Москва", "geo": "Москва"},
        {"id": "@pik_dom_moscow", "name": "ПИК Москва", "geo": "Москва"},
        {"id": "@lengradom_chat", "name": "Ленградом", "geo": "СПб"},
        {"id": "@metrika_chat", "name": "Метрика", "geo": "Москва"},
        {"id": "@akvatint_chat", "name": "Акватинта", "geo": "Москва"},
        {"id": "@yuzhny_park_chat", "name": "Южный парк", "geo": "Москва"},
        {"id": "@krasnaya_rozha_chat", "name": "Красная Роза", "geo": "Москва"},
        {"id": "@dombud_chat", "name": "Домбуд", "geo": "Москва"},
        {"id": "@forum_chat_moscow", "name": "Форум Чат Москва", "geo": "Москва"},
    ]

    # CONSTRUCTION_HUBS — чаты Подмосковья (для ДОМ ГРАНД)
    CONSTRUCTION_HUBS = [
        {"id": "@new_dom_mo", "name": "Новый Дом МО", "geo": "Московская область"},
        {"id": "@stroyka_mo_chat", "name": "Стройка МО", "geo": "Подмосковье"},
        {"id": "@zagorodmo_chat", "name": "Загород МО", "geo": "Подмосковье"},
        {"id": "@mo_dom_chat", "name": "МО Дом", "geo": "Московская область"},
        {"id": "@kottedjmo_chat", "name": "Коттеджи МО", "geo": "Подмосковье"},
        {"id": "@tehnadzor_mo", "name": "Технадзор МО", "geo": "Подмосковье"},
        {"id": "@remont_mo_chat", "name": "Ремонт МО", "geo": "Подмосковье"},
        {"id": "@stroiproject_mo", "name": "Стройпроект МО", "geo": "Подмосковье"},
    ]

    # GEO_CHATS — все чаты для мониторинга (объединённый список)
    GEO_CHATS = []

    # === ТРИГГЕРНЫЕ ФРАЗЫ ===
    
    LOCAL_INTENT_TRIGGERS = [
        r"(кто\s+(делал|может сделать|посоветует|знает))",
        r"(посоветуйте\s+(мастера|подрядчика|дизайнера|архитектора))",
        r"(ищу\s+(мастера|подрядчика|дизайнера|прораб|строителей))",
        r"(нужен\s+(мастер|подрядчик|дизайнер|прораб))",
        r"(проект\s+(на|для|по))",
        r"(согласование\s+(перепланировки|проекта))",
        r"(перепланировк[ау])",
        r"(\bremont\b|\brepair\b)",
        r"(ремонт\s+(квартиры|дома|офиса))",
        r"(строительств[ао]|строительные\s+работы)",
        r"(план\s+(помещения|квартиры|дома))",
        r"(сколько\s+(стоит|будет|нужно))",
    ]

    def __init__(self):
        self.monitoring_enabled = os.getenv("COMPETITOR_SPY_ENABLED", "false").lower() == "true"
        self.geo_monitoring_enabled = os.getenv("GEO_SPY_ENABLED", "true").lower() == "true"
        self.check_interval = int(os.getenv("COMPETITOR_SPY_INTERVAL", "3600"))
        self.geo_check_interval = int(os.getenv("GEO_SPY_INTERVAL", "300"))
        
        self.telegram_api_id = os.getenv("TELEGRAM_API_ID", "")
        self.telegram_api_hash = os.getenv("TELEGRAM_API_HASH", "")
        self.telegram_phone = os.getenv("TELEGRAM_PHONE", "")
        
        self.admin_chat_id = int(os.getenv("LEADS_GROUP_CHAT_ID", "-1003370698977"))
        self.hot_leads_thread = int(os.getenv("THREAD_ID_HOT_LEADS", "10"))
        
        self.channels = self._load_channels()
        self.geo_chats = self._load_geo_chats()
        
        logger.info(f"🤖 CompetitorSpy инициализирован. Мониторинг: {'✅' if self.monitoring_enabled else '❌'}, GEO: {'✅' if self.geo_monitoring_enabled else '❌'}")

    def _load_channels(self) -> List[Dict]:
        channels = []
        for i in range(1, 11):
            channel_id = os.getenv(f"COMPETITOR_CHANNEL_{i}_ID", "")
            channel_name = os.getenv(f"COMPETITOR_CHANNEL_{i}_NAME", "")
            channel_topic = os.getenv(f"COMPETITOR_CHANNEL_{i}_TOPIC", "")
            if channel_id and channel_name:
                channels.append({"id": channel_id, "name": channel_name, "topic": channel_topic or "общее"})
        return channels if channels else self._get_default_channels()

    def _load_geo_chats(self) -> List[Dict]:
        geo_chats = []
        for i in range(1, 21):
            chat_id = os.getenv(f"GEO_CHAT_{i}_ID", "")
            chat_name = os.getenv(f"GEO_CHAT_{i}_NAME", "")
            chat_geo = os.getenv(f"GEO_CHAT_{i}_GEO", "")
            if chat_id and chat_name:
                geo_chats.append({"id": chat_id, "name": chat_name, "geo": chat_geo or "Москва/МО"})
        if not geo_chats:
            geo_chats = self.TARGET_GEO_CHATS + self.CONSTRUCTION_HUBS
        return geo_chats

    def _get_default_channels(self) -> List[Dict]:
        return [
            {"id": "@pereplanirovka_moscow", "name": "Перепланировка Москва", "topic": "перепланировка"},
            {"id": "@remont_izmenenia", "name": "Ремонт и изменения", "topic": "перепланировка"},
            {"id": "@kvartira_legal", "name": "Квартира.Юридически", "topic": "перепланировка"},
            {"id": "@stroyka_dom", "name": "Строительство дома", "topic": "строительство"},
            {"id": "@zagorodny_dom", "name": "Загородный дом", "topic": "загородное строительство"},
            {"id": "@tehnadzor_ru", "name": "Технадзор РФ", "topic": "технадзор"},
        ]

    async def scan_geo_chats(self) -> List[LocalLead]:
        if not self.geo_monitoring_enabled:
            return []
        leads = []
        for chat in self.geo_chats:
            try:
                messages = await self._fetch_chat_messages(chat)
                for msg in messages:
                    intent = self.detect_local_intent(msg['text'])
                    if intent:
                        lead = LocalLead(
                            chat_name=chat['name'],
                            chat_id=chat['id'],
                            user_name=msg['user_name'],
                            user_id=msg['user_id'],
                            message=msg['text'],
                            message_url=msg['url'],
                            detected_intent=intent,
                            geo_context=chat['geo'],
                            timestamp=msg['timestamp']
                        )
                        leads.append(lead)
                        logger.info(f"🎯 Лид в {chat['name']}: {intent}")
                        await self.send_lead_alert(lead)
            except Exception as e:
                logger.error(f"❌ Ошибка {chat['name']}: {e}")
        return leads

    def detect_local_intent(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        intent_patterns = {
            "ИЩЕТ_ИСПОЛНИТЕЛЯ": [
                r"кто\s+(делал|может сделать|посоветует|знает)",
                r"посоветуйте\s+(мастера|подрядчика|дизайнера|архитектора)",
                r"ищу\s+(мастера|подрядчика|дизайнера|прораб|строителей)",
                r"нужен\s+(мастер|подрядчик|дизайнер|прораб)",
            ],
            "ПРОЕКТ_И_СОГЛАСОВАНИЕ": [
                r"проект\s+(на|для|по)",
                r"согласование\s+(перепланировки|проекта)",
                r"перепланировк[ау]",
            ],
            "РЕМОНТ_СТРОЙКА": [
                r"\bremont\b|\brepair\b",
                r"ремонт\s+(квартиры|дома|офиса)",
                r"строительств[ао]",
            ],
            "ПЛАН_ДОКУМЕНТЫ": [r"план\s+(помещения|квартиры|дома)"],
            "СТОИМОСТЬ": [r"сколько\s+(стоит|будет|нужно)"],
        }
        for intent, patterns in intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return intent
        return None

    async def _fetch_chat_messages(self, chat: Dict) -> List[Dict]:
        return []

    async def send_lead_alert(self, lead: LocalLead):
        topic_key = "перепланировки"
        if "строительств" in lead.message.lower() or "дом" in lead.message.lower():
            topic_key = "стройки"
        elif "ремонт" in lead.message.lower():
            topic_key = "ремонта"
        
        response_script = self._generate_outreach_response(lead, topic_key)
        
        alert_text = f"""
🔥 ГОРЯЧИЙ ЛИД — ЧАТ {lead.geo_context}

💬 Источник: {lead.chat_name}
👤 От: {lead.user_name}
📍 Гео: {lead.geo_context}

📝 Сообщение:
{lead.message}

🎯 Тип: {lead.detected_intent}
🔗 [Ссылка]({lead.message_url})

━━━━━━━━━━━━━━━━━━━━━━━

📋 ГОТОВЫЙ ОТВЕТ:

{response_script}

━━━━━━━━━━━━━━━━━━━━━━━
"""
        logger.info(f"📨 Алерт: {lead.chat_name} -> {lead.user_name}")

    def _generate_outreach_response(self, lead: LocalLead, topic_key: str = "перепланировки") -> str:
        bot_link = "https://t.me/Parkhovenko_i_kompaniya_bot"
        return f"""Приветствую! Увидела ваш вопрос в чате ЖК по поводу {topic_key}. Мы занимаемся согласованием {topic_key}, как планируемых, так и уже выполненных. Если актуально, мой ИИ-ассистент Антон может проверить ваш план на соответствие СНиПам. Попробуйте: {bot_link}"""

    async def scan_channels(self) -> List[CompetitorPost]:
        if not self.monitoring_enabled:
            return []
        posts = []
        for channel in self.channels:
            try:
                channel_posts = await self._fetch_channel_posts(channel)
                posts.extend(channel_posts)
            except Exception as e:
                logger.error(f"❌ {channel['name']}: {e}")
        return posts

    async def _fetch_channel_posts(self, channel: Dict) -> List[CompetitorPost]:
        return []

    def analyze_trending(self, posts: List[CompetitorPost]) -> List[TrendingTopic]:
        if not posts:
            return []
        topics: Dict[str, TrendingTopic] = {}
        for post in posts:
            topic = self._extract_topic(post.text)
            if topic not in topics:
                topics[topic] = TrendingTopic(topic=topic, source_channels=[], total_engagement=0, post_examples=[])
            topics[topic].source_channels.append(post.channel_name)
            topics[topic].total_engagement += post.engagement_score
        trending = sorted(topics.values(), key=lambda x: x.total_engagement, reverse=True)[:5]
        for item in trending:
            item.recommendations = self._generate_recommendations(item)
        return trending

    def _extract_topic(self, text: str) -> str:
        text_lower = text.lower()
        keywords = {
            "перепланировка": ["перепланировка", "переустройство", "снос стен"],
            "согласование": ["согласование", "разрешение", "узаконить"],
            "коммерция": ["коммерческое", "нежилое", "магазин", "офис"],
            "загородное": ["дом", "коттедж", "загородный"],
            "технадзор": ["технадзор", "строительный контроль"],
            "риски": ["штраф", "снос", "суд"],
        }
        for topic, kws in keywords.items():
            if any(kw in text_lower for kw in kws):
                return topic
        return "общее"

    def _generate_recommendations(self, topic: TrendingTopic) -> str:
        titles = {"перепланировка": "перепланировке", "согласовании": "процедуре согласования", "коммерции": "коммерческих помещениях", "загородном": "загородном строительстве", "технадзоре": "техническом надзоре", "рисках": "юридических рисках"}
        key = topic.topic if topic.topic in titles else "перепланировке"
        return f"""🔥 {topic.topic.upper()}\n📊 {topic.total_engagement} баллов\n💡 Пост на тему {titles.get(key, topic.topic)} с кейсом ТЕРИОН\n🎯 CTA: @Parkhovenko_i_kompaniya_bot"""

    async def generate_report(self) -> str:
        posts = await self.scan_channels()
        trending = self.analyze_trending(posts)
        if not trending:
            return "🤫 Нет данных."
        lines = ["📊 ОТЧЁТ ШПИОНА", "="*30]
        for i, t in enumerate(trending, 1):
            lines.append(f"{i}. {t.topic.upper()}\n{t.recommendations}")
        return "\n".join(lines) + "\n🤖 CompetitorSpy"


competitor_spy = CompetitorSpy()


async def run_competitor_spy():
    if not competitor_spy.monitoring_enabled:
        logger.info("🤫 Выключен")
        return
    logger.info("🚀 Запущен")
    while True:
        try:
            await competitor_spy.generate_report()
        except Exception as e:
            logger.error(f"❌ {e}")
        await asyncio.sleep(competitor_spy.check_interval)


async def run_geo_spy():
    if not competitor_spy.geo_monitoring_enabled:
        logger.info("🤫 GEO-мониторинг выключен")
        return
    logger.info("🎯 GEO-Spy запущен (каждые 5 мин)")
    while True:
        try:
            leads = await competitor_spy.scan_geo_chats()
            if leads:
                logger.info(f"🎯 Найдено {len(leads)} лидов")
        except Exception as e:
            logger.error(f"❌ GEO Error: {e}")
        await asyncio.sleep(competitor_spy.geo_check_interval)
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
