"""
Scout Parser — снайперский мониторинг жилых ЖК.

Фокус: локальные чаты жилых комплексов (обжитые дома), «горячие» проблемы
перепланировок. Лид = вопрос + технический термин (не «посоветуйте рабочих»).

Приоритетные ЖК: Сердце Столицы, Символ, Зиларт, Пресня Сити, Сити (Башни).
Цели задаются через .env (SCOUT_TG_CHANNEL_1_ID, NAME, GEO) или дефолт ниже.
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
    source_link: Optional[str] = None  # ссылка на чат (для geo_tag из target_resources)


class ScoutParser:
    """
    Scout Agent для парсинга Telegram каналов и VK групп.
    
    Ищет посты по ключевым словам и оставляет комментарии с предложением помощи.
    """

    # === ПРИОРИТЕТНЫЕ ЖК ДЛЯ МОНИТОРИНГА (снайперский режим) ===
    # ID чатов задаются в .env: SCOUT_TG_CHANNEL_1_ID, SCOUT_TG_CHANNEL_1_NAME, SCOUT_TG_CHANNEL_1_GEO и т.д.
    # Если не заданы — используются эти дефолты (id нужно заменить на реальные чаты ЖК).
    TG_CHANNELS = [
        {"id": "", "name": "ЖК «Сердце Столицы»", "geo": "Москва"},
        {"id": "", "name": "ЖК «Символ»", "geo": "Москва"},
        {"id": "", "name": "ЖК «Зиларт»", "geo": "Москва"},
        {"id": "", "name": "ЖК «Пресня Сити»", "geo": "Москва"},
        {"id": "", "name": "Сити (Башни)", "geo": "Москва"},
    ]

    # === VK ГРУППЫ (при необходимости добавить чаты ЖК в VK) ===
    VK_GROUPS = [
        {"id": "235569022", "name": "ТЕРИОН / перепланировки", "geo": "Москва/МО"},
    ]

    # === КЛЮЧЕВЫЕ СЛОВА (в т.ч. боли жильцов) ===
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
        # Боли жильцов ЖК
        "предписание МЖИ",
        "штраф за перепланировку",
        "акт скрытых работ",
        "проект СРО",
        "согласие соседей",
        "мокрая зона",
        # DIY и ремонт
        "своими руками",
        "сломали стену",
        "перенесли радиатор",
        "залили пол",
        "хотим объединить",
    ]

    # === ТЕХНИЧЕСКИЕ ТЕРМИНЫ (Intent: лид только если есть вопрос + один из них) ===
    TECHNICAL_TERMS = [
        r"перепланиров",
        r"согласовани",
        r"узакони",
        r"предписание\s+МЖИ",
        r"МЖИ",
        r"штраф\s+за\s+перепланировку",
        r"акт\s+скрытых\s+работ",
        r"проект\s+СРО",
        r"согласие\s+соседей",
        r"мокрая\s+зона",
        r"снос\s+(стен|подоконн|блока)",
        r"подоконн\w*\s+блок",
        r"объединен",
        r"нежилое\s+помещен",
        r"проект\s+перепланировки",
        r"план\s+(квартир|помещен)",
    ]

    # === ЧЕРНЫЙ СПИСОК (Стоп-слова для фильтрации мусора) ===
    STOP_WORDS = [
        r"продам", r"куплю", r"аренда", r"сдам", r"вакансия", r"ищу\s+работу",
        r"услуги\s+сантехника", r"маникюр", r"ресницы", r"доставка",
        r"скидки", r"акция", r"распродажа", r"подпишись", r"розыгрыш",
        r"крипта", r"инвестиции", r"заработок", r"удаленка",
        r"ремонт\s+телефонов", r"компьютерная\s+помощь",
        r"посоветуйте\s+врача", r"детский\s+сад", r"школа",
    ]

    # === МАРКЕРЫ ДЕЙСТВИЯ (Intent v3.0: живой лид = вопрос + термин + маркер) ===
    COMMERCIAL_MARKERS = [
        r"стоимость",
        r"сколько\s+стоит",
        r"сроки",
        r"цена",
        r"кто\s+делал",
        r"к\s+кому\s+обратиться",
        r"к\s+кому\s+обращались",
        r"предписание",
        r"предписание\s+МЖИ",
        r"МЖИ",
        r"акт",
        r"инспектор",
        r"нужен\s+проект",
        r"заказать\s+проект",
        r"оформить\s+перепланировку",
        r"согласовал\w*",
        r"узаконил\w*",
    ]

    # === МУСОР: отсекаем рекламу и объявления без прямого вопроса к эксперту ===
    JUNK_PHRASES = [
        r"продам",
        r"аренда",
        r"услуги\s+сантехника",
        r"услуги\s+ремонта",
        r"ремонт\s+под\s+ключ",
        r"ремонт\s+квартир\s+под\s+ключ",
        r"вызов\s+сантехника",
        r"вывоз\s+мусора",
        r"мастер\s+на\s+час",
    ]

    # === ПАТТЕРНЫ ВОПРОСА (Intent: считаем лидом только вопрос + термин) ===
    QUESTION_PATTERNS = [
        r"кто\s+(согласовывал|оформлял|делал|заказывал)",
        r"как\s+(согласовать|узаконить|оформить|сделать)",
        r"подскажите\s+(,\s*)?(кто|как|где|можно)",
        r"посоветуйте\s+(,\s*)?(кто|кого|как)",
        r"соседи\s*[,:]",
        r"кто\s*[-–]?\s*нибудь",
        r"есть\s+ли\s+кто",
        r"может\s+кто\s+(знает|сталкивался|делал)",
        r"где\s+(согласовывал|оформлял)",
        r"можно\s+ли\s+(сносит|объединят|переносит)",
        r"\?\s*$",  # заканчивается вопросом
    ]

    # === ТРИГГЕРНЫЕ ФРАЗЫ (расширенные: боли жильцов) ===
    LEAD_TRIGGERS = [
        r"перепланиров",
        r"согласовани",
        r"узакони",
        r"предписание\s+МЖИ",
        r"штраф\s+за\s+перепланировку",
        r"акт\s+скрытых\s+работ",
        r"проект\s+СРО",
        r"согласие\s+соседей",
        r"мокрая\s+зона",
        r"проект",
        r"план\s+(квартир|комнат| помещен)",
        r"снос\s+стен",
        r"снос\s+подоконн",
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
        r"своими\s+руками",
        r"сломали\s+стену",
        r"перенесли\s+радиатор",
        r"залили\s+пол",
        r"хотим\s+объединить",
    ]

    # === ГОРЯЧИЕ ТРИГГЕРЫ (Лид без дополнительных проверок) ===
    HOT_TRIGGERS = [
        r"предписание\s+МЖИ",
        r"узаконить\s+перепланировку",
        r"штраф\s+за\s+перепланировку",
        r"инспектор\s+МЖИ",
        r"согласовать\s+перепланировку",
        r"проект\s+перепланировки",
        r"заказать\s+проект",
        r"нужен\s+проект",
        r"кто\s+согласовывал",
    ]

    def __init__(self):
        self.vk_token = VK_TOKEN
        self.vk_api_version = "5.199"
        
        # Telegram credentials
        self.telegram_api_id = os.getenv("TELEGRAM_API_ID", "")
        self.telegram_api_hash = os.getenv("TELEGRAM_API_HASH", "")
        self.telegram_phone = os.getenv("TELEGRAM_PHONE", "")
        
        # Настройки
        from config import SCOUT_ENABLED, SCOUT_TG_CHANNELS, SCOUT_VK_GROUPS, SCOUT_TG_KEYWORDS, SCOUT_VK_KEYWORDS, SCOUT_VK_REGIONS
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
        self.last_scan_chats_list: List[Dict] = []  # результат scan_all_chats() для импорта в target_resources

        # Anti-Flood: не более одного get_entity в 60 секунд (защита сессии от бана)
        self._get_entity_interval = 60.0
        self._last_get_entity_at = 0.0

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

    def _load_vk_keywords(self) -> List[str]:
        """Загрузка ключевых слов VK из конфига"""
        from config import SCOUT_VK_KEYWORDS
        return SCOUT_VK_KEYWORDS or self.KEYWORDS

    def _load_vk_regions(self) -> List[str]:
        """Загрузка регионов VK из конфига"""
        from config import SCOUT_VK_REGIONS
        return SCOUT_VK_REGIONS or []

    # Минимум слов для «боли» (не мусор, не просто ссылка)
    MIN_WORDS_FOR_LEAD = 5
    # Регулярка: только ссылка (http/https или tg://)
    URL_ONLY_PATTERN = re.compile(
        r"^\s*(https?://[^\s]+\s*|tg://[^\s]+\s*)*\s*$",
        re.IGNORECASE,
    )

    def _is_relevant_post(self, text: str) -> bool:
        """Фильтр мусора: нужны боли, а не упоминания. Меньше 5 слов или только ссылка — игнорируем."""
        if not text or not isinstance(text, str):
            return False
        stripped = text.strip()
        words = [w for w in stripped.split() if w]
        if len(words) < self.MIN_WORDS_FOR_LEAD:
            return False
        # Только ссылки без текста — не лид
        if self.URL_ONLY_PATTERN.match(stripped):
            return False
        return True

    def _has_question(self, text: str) -> bool:
        """Есть ли в тексте вопрос (интент: «ищет ответ/совет»). Игнорируем «Посоветуйте рабочих» без техтерминов."""
        if not text:
            return False
        t = text.strip()
        if not t.endswith("?"):
            t = t + " "
        text_lower = t.lower()
        for pat in self.QUESTION_PATTERNS:
            if re.search(pat, text_lower):
                return True
        return False

    def _has_technical_term(self, text: str) -> bool:
        """Есть ли технический термин (перепланировка, МЖИ, акт скрытых работ и т.д.)."""
        if not text:
            return False
        text_lower = text.lower()
        for pat in self.TECHNICAL_TERMS:
            if re.search(pat, text_lower):
                return True
        keywords = self._load_keywords()
        for kw in keywords:
            if kw.lower() in text_lower:
                return True
        return False

    def _has_commercial_marker(self, text: str) -> bool:
        """Есть ли коммерческий маркер (стоимость, сроки, кто делал, к кому обратиться, предписание)."""
        if not text:
            return False
        text_lower = text.lower()
        for pat in self.COMMERCIAL_MARKERS:
            if re.search(pat, text_lower):
                return True
        return False

    def _has_junk_phrase(self, text: str) -> bool:
        """Сообщение с рекламой/объявлениями без прямого запроса от клиента — отсекаем."""
        if not text:
            return False
        text_lower = text.lower()

        # Проверка JUNK_PHRASES (реклама услуг)
        for pat in self.JUNK_PHRASES:
            if re.search(pat, text_lower):
                return True

        # Проверка STOP_WORDS (общий мусор)
        for pat in self.STOP_WORDS:
            if re.search(pat, text_lower):
                return True

        # Фильтр ботов: слишком много ссылок или капс
        if text.count("http") > 2 or text.count("@") > 2:
            return True

        return False

    def detect_lead(self, text: str, platform: str = "telegram") -> bool:
        """
        Интеллектуальный фильтр (Intent v2.3):
        - Горячие триггеры -> Лид (сразу)
        - Для ВК: ключевые слова -> Лид (сразу)
        - Для ТГ: (Вопрос + Тех.термин) ИЛИ (Тех.термин + Коммерч.маркер) -> Лид
        """
        if not self._is_relevant_post(text):
            return False
        if self._has_junk_phrase(text):
            return False

        text_lower = text.lower()

        # 1. Проверка горячих триггеров (безусловный лид)
        for ht in self.HOT_TRIGGERS:
            if re.search(ht, text_lower):
                return True

        # 2. Специфика ВК (паблики ЖК)
        if platform == "vk":
            vk_kws = self._load_vk_keywords()
            if any(kw.lower() in text_lower for kw in vk_kws):
                return True
            # Если не нашли по ключевым словам, проверяем общую логику ниже

        # 3. Общая логика (расслабленная)
        has_question = self._has_question(text)
        has_tech = self._has_technical_term(text)
        has_comm = self._has_commercial_marker(text)

        # Комбинации для лида
        if has_tech and (has_question or has_comm):
            return True

        # Проверка по триггерам болей (тоже считаем за лид если есть тех. подтекст)
        if has_tech:
            for trigger in self.LEAD_TRIGGERS:
                if re.search(trigger, text_lower):
                    return True

        # Дополнительная проверка по ключевым словам из конфига
        keywords = self._load_vk_keywords() if platform == "vk" else self._load_keywords()
        if has_question or has_comm:
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    return True

        return False

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
        # Названия ЖК из нашего списка
        jk_names = ["сердце столицы", "символ", "зиларт", "пресня сити", "сити", "башн"]
        for jk in jk_names:
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
                break
        if not parts:
            return source_name or ""
        return ", ".join(parts)

    async def generate_ai_outreach(self, post_text: str, source_type: str = "telegram") -> str:
        """Генерация персонализированного сообщения через AI"""
        from utils.router_ai import router_ai

        prompt = f"""
Ты — Антон, ИИ-ассистент компании TERION (эксперты по перепланировкам).
Твоя задача: написать ОЧЕНЬ короткий, вежливый и экспертный комментарий к посту пользователя, который столкнулся with проблемой или вопросом по перепланировке.

Текст поста: "{post_text}"

ТРЕБОВАНИЯ:
1. Максимум 2-3 предложения.
2. Никакого официоза, пиши как живой человек, но профессионально.
3. Упомяни конкретную деталь из его поста (например, если он спросил про "мокрую зону", ответь про нее).
4. Обязательно дай ссылку на бесплатную консультацию в @Parkhovenko_i_kompaniya_bot.
5. Если это Telegram, стиль должен быть более неформальным. Если VK — чуть более сдержанным.

Твой ответ (только текст комментария):"""

        try:
            if router_ai:
                message = await router_ai.generate_response(prompt, model="gpt-4o-mini")
                if message and len(message.strip()) > 10:
                    return message.strip()
        except Exception as e:
            logger.error(f"Ошибка AI генерации outreach: {e}")

        # Fallback
        return self.generate_outreach_message(source_type)

    def generate_outreach_message(self, source_type: str = "telegram", geo: str = "") -> str:
        """Генерация сообщения для комментария/ответа (Fallback)"""
        if source_type == "telegram":
            return (
                "Привет! 👋 Видим ваш вопрос по перепланировке. \n"
                "Мы в TERION помогаем узаконить даже самые сложные случаи. \n"
                "Бесплатный разбор вашей ситуации здесь: @Parkhovenko_i_kompaniya_bot"
            )
        else:
            return (
                "Добрый день! 👋 Специализируемся на согласовании перепланировок. \n"
                "Проверим ваш проект на риски и поможем с документами. \n"
                "Консультация: @Parkhovenko_i_kompaniya_bot"
            )

    def _tg_post_url(self, channel_id, message_id: int) -> str:
        """Ссылка на пост: для username — t.me/username/msg, для -100XXX — t.me/c/num/msg."""
        sid = str(channel_id)
        if sid.startswith("-100"):
            return f"https://t.me/c/{sid.replace('-100', '')}/{message_id}"
        return f"https://t.me/{channel_id}/{message_id}"

    def _channel_id_to_link(self, channel_id) -> str:
        """Ссылка на чат/канал по ID (для сохранения в target_resources)."""
        sid = str(channel_id).strip()
        if sid.startswith("-100"):
            return f"https://t.me/c/{sid.replace('-100', '')}"
        return f"https://t.me/{sid}"

    async def _wait_get_entity_throttle(self) -> None:
        """Ждать до истечения интервала с последнего get_entity (Anti-Flood: 1 запрос / 60 сек)."""
        now = time.monotonic()
        elapsed = now - self._last_get_entity_at
        if elapsed < self._get_entity_interval and self._last_get_entity_at > 0:
            wait = self._get_entity_interval - elapsed
            logger.info("[SCOUT] Пауза %.0f сек до следующей проверки ссылки (anti-flood).", wait)
            await asyncio.sleep(wait)

    async def _throttled_get_entity(self, client, peer):
        """Вызов get_entity с лимитом не чаще 1 раз в 60 секунд."""
        await self._wait_get_entity_throttle()
        entity = await client.get_entity(peer)
        self._last_get_entity_at = time.monotonic()
        return entity

    @staticmethod
    def _extract_tme_links(text: str) -> List[str]:
        """Извлечь из текста ссылки на чаты: t.me/joinchat/..., t.me/name, t.me/c/123."""
        if not text:
            return []
        out = []
        # t.me/joinchat/xxx или t.me/+xxx
        for m in re.finditer(r"https?://(?:www\.)?t\.me/(?:joinchat/|\+)([a-zA-Z0-9_-]+)", text, re.IGNORECASE):
            out.append(f"https://t.me/joinchat/{m.group(1)}")
        # t.me/username (без суффикса /123 — это уже пост)
        for m in re.finditer(r"https?://(?:www\.)?t\.me/([a-zA-Z][a-zA-Z0-9_]{4,})(?:/|$|\s)", text, re.IGNORECASE):
            out.append(f"https://t.me/{m.group(1)}")
        # t.me/c/1234567890
        for m in re.finditer(r"https?://(?:www\.)?t\.me/c/(\d+)(?:/|$|\s)", text, re.IGNORECASE):
            out.append(f"https://t.me/c/{m.group(1)}")
        return list(dict.fromkeys(out))

    # === TELEGRAM PARSING ===

    async def parse_telegram(self, db=None) -> List[ScoutPost]:
        """
        Парсинг Telegram. Если передан db:
        - Список чатов берётся из БД: get_active_targets_for_scout(platform='telegram').
        - Режим «Разведка»: чаты, в которых увидели сообщения и которых нет в target_resources, добавляются со статусом pending.
        - Ловля ссылок: из текста извлекаются t.me/..., простукиваются и при успехе добавляются в target_resources со статусом pending и participants_count.
        """
        if db:
            await self._sync_hardcoded_targets(db)
        from telethon import TelegramClient
        from telethon.tl.types import Channel, Chat
        from config import API_ID, API_HASH

        posts = []
        try:
            from session_manager import SESSION_FILE
            client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
            await client.connect()
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Telegram: {e}")
            return []

        if not await client.is_user_authorized():
            logger.error("❌ Антон не авторизован в Telegram!")
            print("\n⚠️ ВНИМАНИЕ: Требуется авторизация аккаунта для шпиона.")
            print("👉 Запустите команду: python3 session_manager.py")
            print("После успешного ввода кода из Telegram перезапустите бота.\n")
            await client.disconnect()
            return []

        tg_limit = int(os.getenv("SCOUT_TG_MESSAGES_LIMIT", "50"))
        existing_links = set()
        new_links_queue: List[str] = []  # очередь ссылок для проверки по одной (anti-flood)
        if db:
            try:
                resources = await db.get_target_resources(resource_type="telegram", active_only=False)
                existing_links = {(r.get("link") or "").strip().rstrip("/") for r in resources if r.get("link")}
            except Exception as e:
                logger.warning("Не удалось загрузить target_resources для разведки: %s", e)

        # Список чатов: из БД (data-driven) или из конфига
        channels_to_scan = []
        if db:
            try:
                targets = await db.get_active_targets_for_scout(platform="telegram")
                for t in targets:
                    link = (t.get("link") or "").strip().rstrip("/")
                    if not link:
                        continue
                    try:
                        entity = await self._throttled_get_entity(client, link)
                        cid = getattr(entity, "id", None)
                        if cid is None:
                            continue
                        channels_to_scan.append({
                            "id": cid,
                            "name": t.get("title") or link,
                            "geo": t.get("geo_tag") or "",
                            "link": link,
                            "last_post_id": t.get("last_post_id") or 0,
                            "db_id": t.get("id")
                        })
                    except Exception as e:
                        logger.warning("Не удалось разрешить чат %s: %s", link, e)
            except Exception as e:
                logger.warning("Не удалось загрузить активные цели из БД: %s", e)
        if not channels_to_scan:
            channels_to_scan = [
                {"id": ch.get("id"), "name": ch.get("name"), "geo": ch.get("geo", ""), "link": "", "last_post_id": 0, "db_id": None}
                for ch in self.tg_channels if str(ch.get("id") or "").strip()
            ]

        if not channels_to_scan:
            logger.warning("⚠️ Не найдено активных каналов для сканирования! Проверьте базу данных или .env (SCOUT_TG_CHANNEL_X_ID)")

        for channel in channels_to_scan:
            cid = channel.get("id")
            if cid is None:
                continue
            count = 0
            scanned = 0
            last_post_id = channel.get("last_post_id", 0)
            max_id = last_post_id

            try:
                # Используем min_id для загрузки только новых сообщений
                iter_params = {"limit": tg_limit}
                if last_post_id > 0:
                    iter_params["min_id"] = last_post_id
                    logger.debug(f"[SCOUT] Канал {channel['name']}: инкрементальный скан от ID {last_post_id}")
                else:
                    # Прогревочный скан если база пуста: берем последние 20 сообщений
                    iter_params["limit"] = 20
                    logger.info(f"[SCOUT] Канал {channel['name']}: прогревочный скан (первый запуск)")

                async for message in client.iter_messages(cid, **iter_params):
                    if not message.text:
                        continue
                    if message.id > max_id:
                        max_id = message.id
                    scanned += 1
                    # Ловля ссылок: ставим в очередь, обрабатываем по одной с паузой 60 сек (anti-flood)
                    if db:
                        for url in self._extract_tme_links(message.text):
                            url_norm = url.rstrip("/")
                            if url_norm in existing_links:
                                continue
                            if url_norm not in {u.rstrip("/") for u in new_links_queue}:
                                new_links_queue.append(url_norm)
                                print("[SCOUT] Найдена новая ссылка, поставлена в очередь на проверку через 60 сек.", flush=True)
                                logger.info("[SCOUT] Найдена новая ссылка %s, поставлена в очередь на проверку через 60 сек.", url_norm)
                    if self.detect_lead(message.text, platform="telegram"):
                        author_id = getattr(message, "sender_id", None)
                        author_name = None
                        if getattr(message, "sender", None):
                            s = message.sender
                            author_name = getattr(s, "username", None) or getattr(s, "first_name", None)
                            if author_name and getattr(s, "last_name", None):
                                author_name = f"{author_name} {s.last_name}".strip()
                        post = ScoutPost(
                            source_type="telegram",
                            source_name=channel['name'],
                            source_id=str(channel['id']),
                            post_id=str(message.id),
                            text=message.text,
                            author_id=author_id,
                            author_name=author_name,
                            url=self._tg_post_url(cid, message.id),
                            source_link=channel.get("link") or "",
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
                # Обновляем last_post_id в базе данных
                if db and channel.get("db_id") and max_id > channel.get("last_post_id", 0):
                    try:
                        await db.update_last_post_id(channel["db_id"], max_id)
                        logger.info(f"✅ Обновлен last_post_id для {channel['name']}: {max_id}")
                    except Exception as e:
                        logger.warning(f"Не удалось обновить last_post_id для {channel['name']}: {e}")
                # Режим «Разведка»: чат, в котором увидели сообщения и которого нет в базе — добавляем со статусом pending
                if db and cid:
                    link = channel.get("link") or self._channel_id_to_link(cid)
                    link_norm = link.rstrip("/")
                    if link_norm not in existing_links:
                        try:
                            participants = None
                            try:
                                ent = await self._throttled_get_entity(client, cid)
                                participants = getattr(ent, "participants_count", None)
                            except Exception:
                                pass
                            await db.add_target_resource(
                                "telegram", link, title=channel.get("name") or str(cid),
                                notes="Обнаружен автоматически", status="pending", participants_count=participants,
                            )
                            existing_links.add(link_norm)
                            logger.info("🏢 Режим Разведка: добавлен чат %s", link)
                        except Exception as e:
                            logger.debug("Не удалось добавить ресурс %s: %s", link, e)
            except (asyncio.CancelledError, KeyboardInterrupt):
                await client.disconnect()
                raise
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

        # Режим «Тишины»: перед проверкой новых ссылок — пауза 60 сек (защита сессии)
        if new_links_queue:
            logger.info("[SCOUT] Режим тишины: пауза 60 сек перед проверкой %s новых ссылок.", len(new_links_queue))
            print("[SCOUT] Режим тишины: пауза 60 сек перед проверкой новых ссылок.", flush=True)
            await asyncio.sleep(60)
        # Обработка очереди: строго по одной с паузой 60 сек между запросами (anti-flood)
        for url in new_links_queue:
            try:
                entity = await self._throttled_get_entity(client, url)
                if isinstance(entity, (Channel, Chat)):
                    title = getattr(entity, "title", None) or getattr(entity, "username", None) or str(entity.id)
                    if entity.id:
                        link_to_store = self._channel_id_to_link(entity.id)
                    else:
                        link_to_store = url.rstrip("/")
                    if link_to_store.rstrip("/") not in existing_links:
                        participants = getattr(entity, "participants_count", None)
                        if participants is None:
                            try:
                                full = await self._throttled_get_entity(client, entity)
                                participants = getattr(full, "participants_count", None)
                            except Exception:
                                pass
                        await db.add_target_resource(
                            "telegram", link_to_store, title=title,
                            notes="Обнаружен автоматически (ссылка в чате)",
                            status="pending", participants_count=participants,
                        )
                        existing_links.add(link_to_store.rstrip("/"))
                        logger.info("🔗 Добавлен ресурс по ссылке из сообщения: %s", link_to_store)
            except (asyncio.CancelledError, KeyboardInterrupt):
                await client.disconnect()
                raise
            except Exception as e:
                logger.debug("Не удалось разрешить ссылку %s: %s", url, e)

        await client.disconnect()
        return posts

    async def scan_all_chats(self) -> List[Dict]:
        """
        Команда-сканер: пробежаться по всем активным диалогам и чатам Telethon,
        собрать ID, названия и количество участников. Для использования в /scan_chats.
        """
        from telethon import TelegramClient
        from telethon.tl.types import Channel, Chat
        from config import API_ID, API_HASH

        client = TelegramClient('anton_parser', API_ID, API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return []

        result = []
        try:
            async for dialog in client.iter_dialogs(limit=500):
                e = dialog.entity
                chat_id = getattr(e, "id", None)
                if chat_id is None:
                    continue
                title = getattr(e, "title", None) or getattr(e, "first_name", None) or str(chat_id)
                if getattr(e, "last_name", None):
                    title = f"{title} {e.last_name}".strip()
                link = self._channel_id_to_link(chat_id)
                participants = getattr(e, "participants_count", None)
                if participants is None and isinstance(e, (Channel, Chat)):
                    try:
                        full = await client.get_entity(e)
                        participants = getattr(full, "participants_count", None)
                    except Exception:
                        participants = None
                result.append({
                    "id": chat_id,
                    "title": title or "—",
                    "link": link,
                    "participants_count": participants,
                })
        finally:
            await client.disconnect()
        self.last_scan_chats_list = result
        return result

    async def search_public_channels(self, keyword: str) -> List[Dict]:
        """
        Глобальный поиск публичных каналов и групп в Telegram по ключевому слову.
        """
        from telethon import TelegramClient, functions
        from telethon.tl.types import Channel, Chat
        from config import API_ID, API_HASH

        client = TelegramClient('anton_parser', API_ID, API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return []

        results = []
        try:
            # Используем глобальный поиск контактов/каналов
            search_result = await client(functions.contacts.SearchRequest(
                q=keyword,
                limit=20
            ))

            if not search_result or not hasattr(search_result, "chats"):
                return []

            # Используем напрямую список чатов из результата (они уже подгружены)
            for entity in search_result.chats:
                try:
                    if isinstance(entity, (Channel, Chat)) and not getattr(entity, "left", False):
                        cid = entity.id
                        title = getattr(entity, "title", "Без названия")
                        username = getattr(entity, "username", None)
                        participants = getattr(entity, "participants_count", None)

                        # Формируем ссылку
                        if username:
                            link = f"https://t.me/{username}"
                        else:
                            # Для приватных каналов/групп, к которым у нас нет доступа,
                            # id может быть бесполезен для внешней ссылки без /c/,
                            # но для системного ID пойдет
                            link = f"https://t.me/c/{cid}"

                        results.append({
                            "id": cid,
                            "title": title,
                            "link": link,
                            "participants_count": participants,
                            "source_type": "telegram"
                        })
                except Exception as e:
                    logger.debug(f"Ошибка обработки сущности в поиске: {e}")
                    continue
        except Exception as e:
            logger.error(f"Ошибка глобального поиска TG по '{keyword}': {e}")
        finally:
            await client.disconnect()
        return results

    async def search_public_vk_groups(self, keyword: str) -> List[Dict]:
        """
        Глобальный поиск публичных групп в VK по ключевому слову.
        """
        if not self.vk_token:
            return []

        params = {
            "q": keyword,
            "type": "group",
            "count": 20,
            "sort": 0 # по релевантности
        }

        try:
            response = await self._vk_request("groups.search", params)
        except Exception as e:
            logger.error(f"Ошибка API ВК при поиске '{keyword}': {e}")
            return []

        if not response or "items" not in response:
            return []

        results = []
        for item in response["items"]:
            gid = item["id"]
            title = item.get("name", "Без названия")
            screen_name = item.get("screen_name", f"club{gid}")

            results.append({
                "id": str(gid),
                "title": title,
                "link": f"https://vk.com/{screen_name}",
                "participants_count": None, # Можно получить через groups.getById если нужно
                "source_type": "vk"
            })
        return results

    async def resolve_telegram_link(self, link: str) -> Optional[Dict]:
        """
        По ссылке t.me/... получить сущность, название и кол-во участников.
        Для /add_target: сохранить в БД со статусом pending.
        """
        from telethon import TelegramClient
        from telethon.tl.types import Channel, Chat
        from config import API_ID, API_HASH

        link = (link or "").strip().rstrip("/")
        if "t.me" not in link:
            return None
        client = TelegramClient('anton_parser', API_ID, API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            return None
        try:
            await self._wait_get_entity_throttle()
            entity = await client.get_entity(link)
            self._last_get_entity_at = time.monotonic()
            cid = getattr(entity, "id", None)
            title = getattr(entity, "title", None) or getattr(entity, "username", None) or (str(cid) if cid else link)
            participants = getattr(entity, "participants_count", None)
            if participants is None and isinstance(entity, (Channel, Chat)):
                try:
                    await self._wait_get_entity_throttle()
                    full = await client.get_entity(entity)
                    self._last_get_entity_at = time.monotonic()
                    participants = getattr(full, "participants_count", None)
                except Exception:
                    pass
            stored_link = self._channel_id_to_link(cid) if cid else link
            return {"id": cid, "title": title, "link": stored_link, "participants_count": participants}
        except Exception as e:
            logger.warning("resolve_telegram_link %s: %s", link, e)
            return None
        finally:
            await client.disconnect()

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

    async def parse_vk(self, db=None) -> List[ScoutPost]:
        """
        Парсинг VK групп.
        
        Ищет посты по ключевым словам, оставляет комментарии.
        """
        if db:
            await self._sync_hardcoded_targets(db)
        if not self.enabled:
            logger.info("🔍 Scout VK: выключен")
            return []
        
        if not self.vk_token:
            logger.error("❌ VK_TOKEN не настроен")
            return []
        
        # Список групп: из БД или из конфига
        groups_to_scan = []
        if db:
            try:
                targets = await db.get_active_targets_for_scout(platform="vk")
                for t in targets:
                    link = t.get("link", "")
                    # Извлекаем ID из ссылки vk.com/group_id или vk.com/public_id
                    match = re.search(r"vk\.com/(?:club|public|group)?(\d+)", link)
                    gid = match.group(1) if match else t.get("id")
                    if gid:
                        groups_to_scan.append({
                            "id": str(gid),
                            "name": t.get("title") or link,
                            "geo": t.get("geo_tag") or "Москва/МО",
                            "db_id": t.get("id")
                        })
            except Exception as e:
                logger.warning("Не удалось загрузить активные VK цели из БД: %s", e)

        if not groups_to_scan:
            groups_to_scan = self.vk_groups

        logger.info(f"🔍 Сканирование {len(groups_to_scan)} VK групп...")

        posts = []
        # Сколько постов брать для разбора комментариев
        vk_posts_to_scan = int(os.getenv("SCOUT_VK_POSTS_FOR_COMMENTS", "10"))
        vk_comments_per_post = int(os.getenv("SCOUT_VK_COMMENTS_PER_POST", "30"))

        for group in groups_to_scan:
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
                    if self.detect_lead(text, platform="vk"):
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
                        if not ctext or not self.detect_lead(ctext, platform="vk"):
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
                if count > 0 and db:
                    try:
                        await db.set_setting("scout_vk_lead_" + str(group["id"]), datetime.now().isoformat())
                    except Exception:
                        pass
            except (asyncio.CancelledError, KeyboardInterrupt):
                raise
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

    async def _sync_hardcoded_targets(self, db):
        """Синхронизация захардкоженных каналов с БД для корректного трекинга last_post_id."""
        if not db:
            return
        try:
            # TG
            for ch in self.TG_CHANNELS:
                if not ch.get("id"): continue
                link = self._channel_id_to_link(ch["id"])
                existing = await db.get_target_resource_by_link(link)
                if not existing:
                    await db.add_target_resource("telegram", link, title=ch["name"], geo_tag=ch["geo"], status="active")
                    logger.info(f"✅ Авто-регистрация TG: {ch['name']}")
            # VK
            for g in self.VK_GROUPS:
                link = f"https://vk.com/club{g['id']}"
                existing = await db.get_target_resource_by_link(link)
                if not existing:
                    await db.add_target_resource("vk", link, title=g["name"], geo_tag=g["geo"], status="active")
                    logger.info(f"✅ Авто-регистрация VK: {g['name']}")
        except Exception as e:
            logger.warning(f"Ошибка синхронизации таргетов: {e}")

    async def scan_all(self, db=None) -> List[ScoutPost]:
        """Полное сканирование всех источников. Заполняет last_scan_report."""
        self.last_scan_report = []
        self.last_scan_at = datetime.now()
        all_posts = []

        try:
            tg_posts = await self.parse_telegram(db=db)
            all_posts.extend(tg_posts)
        except Exception as e:
            logger.error(f"❌ TG scan error: {e}")

        try:
            vk_posts = await self.parse_vk(db=db)
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
    
    from database.db import db

    while True:
        try:
            posts = await scout_parser.scan_all(db=db)
            if posts:
                logger.info(f"🔍 Найдено {len(posts)} лидов")
        except Exception as e:
            logger.error(f"❌ Scout error: {e}")
        
        await asyncio.sleep(scout_parser.check_interval)
