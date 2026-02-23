"""
Scout Parser — глобальный поиск лидов с гео-фильтрацией.

Стратегия «Глобальный поиск»:
- Ищет по ключевым словам в любых открытых каналах
- Гео-фильтрация: только Москва и Московская область
- Не привязан к конкретным ЖК
- Discovery автоматически находит новые каналы

Лид = вопрос о перепланировке + технический термин (не «посоветуйте рабочих»).
Цели задаются через .env (SCOUT_TG_CHANNEL_1_ID, NAME, GEO) или через Discovery.
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
    is_comment: bool = False  # True если это комментарий из Discussion Group
    original_channel_id: Optional[str] = None  # ID оригинального канала для комментариев
    likes: int = 0
    comments: int = 0
    source_link: Optional[str] = None  # ссылка на чат (для geo_tag из target_resources)


class ScoutParser:
    """
    Scout Agent для парсинга Telegram каналов и VK групп.
    
    Ищет посты по ключевым словам и оставляет комментарии с предложением помощи.
    """

    # === ДЕФОЛТНЫЕ КАНАЛЫ (если не заданы через .env) ===
    # ВАЖНО: Discovery автоматически находит каналы по ключевым словам.
    # Этот список используется только если каналы не заданы вручную.
    # Гео-фильтрация (Москва/МО) применяется на этапе анализа постов.
    TG_CHANNELS = [
        # Пусто — Discovery найдёт каналы автоматически
    ]

    # === VK ГРУППЫ ===
    # Наша собственная группа ТЕРИОН намеренно исключена —
    # шпион ищет клиентов во внешних источниках, не у себя.
    # Добавьте сюда VK-группы ЖК или тематические сообщества если нужно.
    VK_GROUPS: list = []

    # === STOP_KEYWORDS: Черный список для жесткой фильтрации (до отправки в ИИ) ===
    # Если любое из этих слов встречается в тексте — пост/комментарий удаляется до этапа отправки в нейросеть (экономия токенов)
    STOP_KEYWORDS = [
        "генеалогия",
        "РГАДА",
        "архив",
        "архивные документы",
        "съезд партии",
        "партия",
        "волейбол",
        "волейбольный турнир",
        "футбол",
        "вакансия",
        "аренда",
        "съезд",
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
        # Расширенные паттерны для реальных лидов
        "нужен проект перепланировки",
        "узаконить перепланировку в новостройке",
        "объединить кухню и комнату",
        "перенос мокрой зоны",
        "разрешение на перепланировку",
        "узаконить перепланировку без проекта",
        "сделали проем в несущей стене",
        "несущая стена",
        "БТИ",
        "проектировщик",
        "согласование перепланировки",
        "жилищная инспекция",
        "смежная стена",
        "монолит",
        "панельный дом",
        "проектная организация",
        "акты скрытых работ",
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
        # Расширенные технические термины
        r"несущ\w*\s+стен",
        r"бти",
        r"проектировщик",
        r"жилищн\w*\s+инспекц",
        r"смежн\w*\s+стен",
        r"монолит",
        r"панельн\w*\s+дом",
        r"проектн\w*\s+организац",
        r"акт\w*\s+скрыт\w*\s+работ",
        r"объедин\w*\s+(кухн|комнат|ванн)",
        r"перенос\w*\s+мокр\w*\s+зон",
        r"проем\w*\s+в\w*\s+несущ",
        r"разрешен\w*\s+на\w*\s+перепланиров",
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
        # Расширенные коммерческие маркеры
        r"к\s+кому\s+обратиться",
        r"сколько\s+стоит",
        r"сделаете\?",
        r"делали\s+ли\s+кто\s*[-–]?\s*то",
        r"подскажите\s+компани",
        r"есть\s+контакт",
        r"ищу\s+исполнител",
        r"готов\s+заплатит",
        r"срочно",
        r"нужна\s+помощь",
        r"помогите",
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
        # Расширенные паттерны вопросов
        r"как\s+оформить",
        r"что\s+нужно",
        r"что\s+требуется",
        r"что\s+делать",
        r"подскажите\s+пожалуйста",
        r"помогите",
        r"нужна\s+консультац",
        r"кто\s+знает",
        r"кто\s+сталкивался",
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
    
    # ── HOT_TRIGGERS: Критические фразы для немедленного определения лида ──────────
    # Если найдена любая из этих фраз - лид считается горячим без дополнительных проверок
    HOT_TRIGGERS = [
        r"предписание\s+МЖИ",
        r"узаконить",
        r"МЖИ",
        r"предписание",
        r"инспектор\s+МЖИ",
        r"пришла\s+МЖИ",
        r"штраф\s+БТИ",
        r"штраф\s+за\s+перепланировку",
        r"блокировка\s+сделки",
        r"суд\s+по\s+перепланировке",
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
        
        # Отладочный режим
        self.debug_mode = os.getenv("SCOUT_DEBUG", "false").lower() == "true"
        self.debug_limit = int(os.getenv("SCOUT_DEBUG_LIMIT", "10"))  # Сколько сообщений логировать в debug режиме

        # Каналы и группы: сначала детальный .env (SCOUT_TG_CHANNEL_1_ID и т.д.), иначе список из .env, иначе дефолт (Москва/МО)
        self.tg_channels = self._load_tg_channels()
        if not self.tg_channels and SCOUT_TG_CHANNELS:
            self.tg_channels = [{"id": c.strip(), "name": c.strip(), "geo": "Москва/МО"} for c in SCOUT_TG_CHANNELS if c and c.strip()]
        if not self.tg_channels:
            self.tg_channels = self.TG_CHANNELS

        # ── VK ГРУППЫ: Инициализация пустым списком ────────────────────────────────────
        # Реальная загрузка из БД происходит асинхронно в parse_vk() через _load_vk_groups(db=db)
        # Здесь инициализируем fallback из .env для обратной совместимости
        self.vk_groups = []
        if SCOUT_VK_GROUPS:
            self.vk_groups = [{"id": g.strip(), "name": g.strip(), "geo": "Москва/МО"} for g in SCOUT_VK_GROUPS if g and g.strip()]
        if not self.vk_groups:
            self.vk_groups = self.VK_GROUPS

        # Отчёт последнего скана: где был шпион, куда удалось попасть
        self.last_scan_report = []  # list of {"type", "name", "id", "status": "ok"|"error", "posts": N, "scanned": N, "error": str|None}
        self.last_scan_at: Optional[datetime] = None
        self.last_scan_chats_list: List[Dict] = []  # результат scan_all_chats() для импорта в target_resources
        
        # Статистика для отчётов
        self.total_scanned = 0  # Всего просмотрено сообщений
        self.total_with_keywords = 0  # С ключевыми словами
        self.total_leads = 0  # Найдено лидов
        self.total_hot_leads = 0  # Горячих лидов

        # Anti-Flood: разные интервалы для проверенных и новых источников
        self._get_entity_interval_verified = 5.0  # 5 секунд для проверенных источников (из БД)
        self._get_entity_interval_new = 60.0  # 60 секунд для новых источников (Discovery)
        self._get_entity_interval = self._get_entity_interval_verified  # По умолчанию используем короткий интервал
        self._last_get_entity_at = 0.0
        self._is_verified_source = False  # Флаг для определения типа источника

        # ── ЛОГИРОВАНИЕ: Используем fallback из .env для подсчёта VK групп ─────────────
        # Реальная загрузка из БД произойдёт в parse_vk(), здесь показываем только fallback
        vk_groups_count = len(self.vk_groups) if isinstance(self.vk_groups, list) else 0
        logger.info(f"🔍 ScoutParser инициализирован. Включен: {'✅' if self.enabled else '❌'}. TG каналов: {len(self.tg_channels)}, VK групп (fallback из .env): {vk_groups_count}. Debug: {'✅' if self.debug_mode else '❌'}")

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

    async def _load_vk_groups(self, db=None) -> List[Dict]:
        """Загрузка VK групп из БД target_resources (приоритет) или .env (fallback).
        
        Args:
            db: Опциональный объект БД для загрузки из target_resources
        
        Returns:
            List[Dict]: Список групп с полями id, name, geo
        """
        groups = []
        
        # ── ПРИОРИТЕТ: Загрузка из БД target_resources ────────────────────────────
        if db:
            try:
                vk_resources = await db.get_target_resources(resource_type="vk", active_only=True)
                for resource in vk_resources:
                    # Извлекаем ID группы из link (может быть числом или ссылкой vk.com/club123)
                    link = resource.get("link", "").strip()
                    group_id = None
                    
                    # Парсим ID из разных форматов ссылок
                    if link.isdigit():
                        group_id = link
                    elif "vk.com" in link or "vk.ru" in link:
                        # Извлекаем ID из ссылки типа vk.com/club123 или vk.com/group123
                        import re
                        match = re.search(r'(?:club|group|public)(\d+)', link)
                        if match:
                            group_id = match.group(1)
                        else:
                            # Пробуем извлечь числовой ID из пути
                            match = re.search(r'/(\d+)', link)
                            if match:
                                group_id = match.group(1)
                    elif link:
                        # Если link не ссылка, возможно это уже ID
                        group_id = link.lstrip("-")
                    
                    if group_id:
                        title = resource.get("title") or resource.get("name") or link
                        geo = resource.get("geo_tag") or "Москва/МО"
                        is_high_priority = resource.get("is_high_priority") or 0
                        groups.append({
                            "id": group_id,
                            "name": title,
                            "geo": geo,
                            "is_high_priority": bool(is_high_priority),  # Приоритетный ЖК из БД
                            "db_id": resource.get("id"),  # ID записи в БД для обновления
                        })
                
                if groups:
                    logger.info(f"📊 Загружено {len(groups)} VK групп из БД target_resources")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка загрузки VK групп из БД: {e}. Используем .env fallback.")
        
        # ── FALLBACK: Загрузка из .env ─────────────────────────────────────────────
        if not groups:
            for i in range(1, 11):
                group_id = os.getenv(f"SCOUT_VK_GROUP_{i}_ID", "")
                group_name = os.getenv(f"SCOUT_VK_GROUP_{i}_NAME", "")
                group_geo = os.getenv(f"SCOUT_VK_GROUP_{i}_GEO", "")
                if group_id and group_name:
                    groups.append({
                        "id": group_id,
                        "name": group_name,
                        "geo": group_geo or "Москва/МО",
                        "is_high_priority": False,  # По умолчанию не приоритетный
                        "db_id": None,
                    })
            
            # Дефолтные группы если не настроены
            if not groups:
                groups = [{
                    **g,
                    "is_high_priority": False,
                    "db_id": None,
                } for g in self.VK_GROUPS]
        
        return groups

    def _load_keywords(self) -> List[str]:
        """Загрузка ключевых слов из .env"""
        keywords_str = os.getenv("SCOUT_KEYWORDS", "")
        if keywords_str:
            return [k.strip() for k in keywords_str.split(",") if k.strip()]
        return self.KEYWORDS

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
        for pat in self.JUNK_PHRASES:
            if re.search(pat, text_lower):
                return True
        return False

    def detect_lead(self, text: str) -> bool:
        """
        Умный поиск лидов (Intent v3.0): 
        - STOP_KEYWORDS: жесткая фильтрация до отправки в ИИ (экономия токенов)
        - HOT_TRIGGERS: если найдена критическая фраза - лид сразу
        - Смягченные фильтры: лид = [Тех. термин] + [Вопрос ИЛИ Коммерческий маркер]
        Отсекаем мусор: «продам», «услуги сантехника», «ремонт под ключ» и т.п.
        """
        # ── ЛОГИРОВАНИЕ: Отслеживание анализа текста в реальном времени ─────────────
        logger.info(f"--- Начинаю анализ текста: {text[:50]}...")
        
        if not text or not self._is_relevant_post(text):
            return False
        
        text_lower = text.lower()
        
        # ── STOP_KEYWORDS: Жесткая фильтрация до отправки в ИИ ──────────────────────
        for stop_keyword in self.STOP_KEYWORDS:
            if stop_keyword.lower() in text_lower:
                logger.debug(f"🚫 STOP_KEYWORD обнаружен: '{stop_keyword}' → пост отфильтрован до отправки в ИИ")
                return False
        
        # ── HOT_TRIGGERS: Критические фразы - лид сразу ──────────────────────────────
        for hot_trigger in self.HOT_TRIGGERS:
            if re.search(hot_trigger, text_lower):
                logger.debug(f"🔥 HOT_TRIGGER обнаружен: {hot_trigger} → ГОРЯЧИЙ ЛИД")
                return True
        
        # Отсекаем мусор
        if self._has_junk_phrase(text):
            return False
        
        # ── СМЯГЧЕННЫЕ ФИЛЬТРЫ: [Тех. термин] + [Вопрос ИЛИ Коммерческий маркер] ────
        has_technical_term = self._has_technical_term(text)
        has_question = self._has_question(text)
        has_commercial_marker = self._has_commercial_marker(text)
        
        # Лид засчитывается, если есть технический термин И (вопрос ИЛИ коммерческий маркер)
        if has_technical_term and (has_question or has_commercial_marker):
            # Дополнительная проверка на триггеры
            for trigger in self.LEAD_TRIGGERS:
                if re.search(trigger, text_lower):
                    return True
            for keyword in self._load_keywords():
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

    def _channel_id_to_link(self, channel_id) -> str:
        """Ссылка на чат/канал по ID (для сохранения в target_resources)."""
        sid = str(channel_id).strip()
        if sid.startswith("-100"):
            return f"https://t.me/c/{sid.replace('-100', '')}"
        return f"https://t.me/{sid}"

    async def _wait_get_entity_throttle(self, is_verified: bool = False) -> None:
        """Ждать до истечения интервала с последнего get_entity.
        
        Args:
            is_verified: True если источник проверенный (из БД), False если новый (Discovery)
        """
        # Выбираем интервал в зависимости от типа источника
        interval = self._get_entity_interval_verified if is_verified else self._get_entity_interval_new
        
        now = time.monotonic()
        elapsed = now - self._last_get_entity_at
        if elapsed < interval and self._last_get_entity_at > 0:
            wait = interval - elapsed
            source_type = "проверенный" if is_verified else "новый"
            logger.info("[SCOUT] Пауза %.0f сек до следующей проверки ссылки (%s источник, anti-flood).", wait, source_type)
            await asyncio.sleep(wait)

    async def _throttled_get_entity(self, client, peer, is_verified: bool = False):
        """Вызов get_entity с лимитом (5 сек для проверенных, 60 сек для новых).
        
        Args:
            client: Telethon client
            peer: Peer для получения entity
            is_verified: True если источник проверенный (из БД), False если новый (Discovery)
        """
        await self._wait_get_entity_throttle(is_verified=is_verified)
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
        - Список чатов берётся из БД: get_active_targets_for_scout() (status='active', platform='telegram').
        - Режим «Разведка»: чаты, в которых увидели сообщения и которых нет в target_resources, добавляются со статусом pending.
        - Ловля ссылок: из текста извлекаются t.me/..., простукиваются и при успехе добавляются в target_resources со статусом pending и participants_count.
        """
        from telethon import TelegramClient
        from telethon.tl.types import Channel, Chat
        from config import API_ID, API_HASH

        posts = []
        client = TelegramClient('anton_parser', API_ID, API_HASH)

        await client.connect()
        if not await client.is_user_authorized():
            logger.error("❌ Антон не авторизован в Telegram!")
            return []

        # ── ИНКРЕМЕНТАЛЬНЫЙ ПОИСК: Используем last_post_id из БД ─────────────────
        # Если SPY_SKIP_OLD_MESSAGES не задан или = 0, используем last_post_id для каждого ресурса
        skip_old_messages = int(os.getenv("SPY_SKIP_OLD_MESSAGES", "0"))
        # Используем глобальный SCAN_LIMIT из config.py или дефолт 100
        from config import SCAN_LIMIT
        tg_limit = int(os.getenv("SCOUT_TG_MESSAGES_LIMIT", str(SCAN_LIMIT)))
        existing_links = set()
        resource_last_post_ids = {}  # Словарь: link -> last_post_id для инкрементального поиска
        new_links_queue: List[str] = []  # очередь ссылок для проверки по одной (anti-flood)
        if db:
            try:
                resources = await db.get_target_resources(resource_type="telegram", active_only=False)
                existing_links = {(r.get("link") or "").strip().rstrip("/") for r in resources if r.get("link")}
                # Загружаем last_post_id для каждого ресурса
                for r in resources:
                    link = (r.get("link") or "").strip().rstrip("/")
                    last_post_id = r.get("last_post_id") or 0
                    if link and last_post_id > 0:
                        resource_last_post_ids[link] = last_post_id
            except Exception as e:
                logger.warning("Не удалось загрузить target_resources для разведки: %s", e)

        # Фильтр «Свой-Чужой»: собственные каналы TERION/Юлии исключаем из сканирования.
        # Чтобы добавить новый канал — укажи его в .env как OWN_CHANNEL_IDS (через запятую).
        from config import (
            CHANNEL_ID_TERION, CHANNEL_ID_DOM_GRAD, NOTIFICATIONS_CHANNEL_ID,
            LEADS_GROUP_CHAT_ID as _LEADS_GROUP_CHAT_ID,
            THREAD_ID_LOGS, BOT_TOKEN,
        )
        _own_ids: set[int] = {
            abs(CHANNEL_ID_TERION),
            abs(CHANNEL_ID_DOM_GRAD),
            abs(NOTIFICATIONS_CHANNEL_ID),
            abs(_LEADS_GROUP_CHAT_ID),
        }
        _extra = os.getenv("OWN_CHANNEL_IDS", "")
        for _raw in _extra.split(","):
            _raw = _raw.strip()
            if _raw.lstrip("-").isdigit():
                _own_ids.add(abs(int(_raw)))

        async def _notify_logs_topic(msg: str):
            """Отправить системное сообщение в топик «Логи» рабочей группы."""
            try:
                from aiogram import Bot
                from aiogram.client.default import DefaultBotProperties
                _bot = None
                try:
                    from utils.bot_config import get_main_bot
                    _bot = get_main_bot()
                except Exception:
                    pass
                if _bot is None and BOT_TOKEN:
                    _bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
                if _bot:
                    await _bot.send_message(
                        _LEADS_GROUP_CHAT_ID,
                        msg,
                        message_thread_id=THREAD_ID_LOGS,
                        parse_mode="HTML",
                    )
            except Exception as _log_err:
                logger.debug("Не удалось отправить в топик Логи: %s", _log_err)

        # Список чатов: из БД (data-driven) или из конфига
        channels_to_scan = []
        if db:
            try:
                targets = await db.get_active_targets_for_scout()
                for t in targets:
                    link = (t.get("link") or "").strip().rstrip("/")
                    if not link:
                        continue
                    try:
                        # Проверенные источники из БД: используем короткий интервал (5 сек)
                        is_verified = t.get("db_id") is not None  # Если есть db_id - это проверенный источник
                        entity = await self._throttled_get_entity(client, link, is_verified=is_verified)
                        cid = getattr(entity, "id", None)
                        if cid is None:
                            logger.warning(
                                "⚠️ Чат разрешён, но entity.id == None: %s (тип: %s). "
                                "Возможно, это медиа-канал без числового ID.",
                                link, type(entity).__name__,
                            )
                            continue
                        # Фильтр «Свой-Чужой»
                        if abs(cid) in _own_ids:
                            logger.info("⏭️ Пропуск собственного канала TERION: %s (id=%s)", link, cid)
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
                        err_str = str(e).lower()
                        is_private = (
                            "no user has username" in err_str
                            or "username not occupied" in err_str
                            or "channel invalid" in err_str
                            or "chat not found" in err_str
                        )
                        is_invite = "+joinchat" in link or "/+" in link

                        if is_private and is_invite:
                            msg_text = (
                                f"🔒 <b>Нужна помощь человека</b>\n\n"
                                f"Чат: <code>{link}</code>\n"
                                f"Статус: <b>ПРИВАТНАЯ ССЫЛКА-ПРИГЛАШЕНИЕ</b>\n"
                                f"Действие: войдите в чат вручную с аккаунта TELEGRAM_PHONE, "
                                f"затем шпион продолжит мониторинг.\n"
                                f"Ошибка: <code>{e}</code>"
                            )
                            logger.error("🔒 ПРИВАТНАЯ ССЫЛКА-ПРИГЛАШЕНИЕ: %s — Ошибка: %s", link, e)
                            await _notify_logs_topic(msg_text)
                        elif is_private:
                            msg_text = (
                                f"❌ <b>Нужна помощь человека</b>\n\n"
                                f"Чат: <code>{link}</code>\n"
                                f"Статус: <b>НЕСУЩЕСТВУЮЩИЙ USERNAME</b>\n"
                                f"Действие: проверьте правильность ссылки или замените "
                                f"на числовой chat_id через @userinfobot.\n"
                                f"Ошибка: <code>{e}</code>"
                            )
                            logger.error("❌ НЕСУЩЕСТВУЮЩИЙ USERNAME: %s — Ошибка: %s", link, e)
                            await _notify_logs_topic(msg_text)
                        else:
                            msg_text = (
                                f"⚠️ <b>Чат недоступен</b>\n\n"
                                f"Чат: <code>{link}</code>\n"
                                f"Ошибка: <code>{e}</code>\n"
                                f"Если закрытая группа — добавьте аккаунт-парсер вручную."
                            )
                            logger.error("⚠️ Не удалось разрешить чат %s: %s", link, e)
                            await _notify_logs_topic(msg_text)
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
            max_id = channel.get("last_post_id", 0)
            
            # ── Проверка Discussion Group (чат для комментариев) ──────────────────
            discussion_group_id = None
            try:
                from telethon.tl.functions.channels import GetFullChannelRequest
                from telethon.tl.types import Channel
                
                # Проверенные источники из БД: используем короткий интервал (5 сек)
                is_verified = channel.get("db_id") is not None
                entity = await self._throttled_get_entity(client, cid, is_verified=is_verified)
                if isinstance(entity, Channel):
                    full_channel = await client(GetFullChannelRequest(entity))
                    if full_channel.full_chat.linked_chat_id:
                        discussion_group_id = full_channel.full_chat.linked_chat_id
                        logger.info(f"💬 Discovery: у канала {channel.get('name')} найден Discussion Group (ID: {discussion_group_id})")
            except Exception as e:
                logger.debug(f"Discussion Group не найден для канала {cid}: {e}")
            
            try:
                # ── ИНКРЕМЕНТАЛЬНЫЙ ПОИСК: Используем last_post_id из БД ────────────────
                # Если last_post_id == 0, делаем прогревочный скан последних 20 сообщений
                # В остальных случаях — строго от последнего ID в базе
                iter_params = {"limit": tg_limit}
                
                if skip_old_messages > 0:
                    # Режим пропуска старых сообщений (для первого запуска или тестирования)
                    logger.debug(f"⏭️ Режим пропуска старых сообщений: skip_old_messages={skip_old_messages}")
                elif max_id == 0:
                    # ── ПРОГРЕВОЧНЫЙ СКАН: Для новых каналов сканируем последние 20 сообщений ──
                    iter_params["limit"] = 20
                    logger.info(f"🔥 Прогревочный скан для нового канала {channel.get('name')}: последние 20 сообщений")
                elif max_id > 0:
                    # Инкрементальный режим: сканируем только сообщения после last_post_id
                    iter_params["min_id"] = max_id
                    logger.debug(f"🔄 Инкрементальный поиск для {channel.get('name')}: min_id={max_id}")
                
                # ── ПАРСИНГ ОСНОВНОГО КАНАЛА: используем SearchRequest для "тихого" просмотра ────────
                # SearchRequest позволяет обходить некоторые ограничения на просмотр открытых чатов
                # и более эффективно искать сообщения по ключевым словам
                messages_list = []
                debug_count = 0
                
                try:
                    # Пробуем использовать SearchRequest для поиска по ключевым словам
                    from telethon.tl.functions.messages import SearchRequest
                    
                    # Используем первые 3 ключевых слова для поиска
                    search_keywords = self._load_keywords()[:3]
                    
                    for keyword in search_keywords:
                        try:
                            search_results = await client(SearchRequest(
                                peer=cid,
                                q=keyword,
                                filter=None,
                                min_date=None,
                                max_date=None,
                                offset_id=0,
                                add_offset=0,
                                limit=20,  # Максимум 20 сообщений на ключевое слово
                                max_id=0,
                                min_id=max_id if max_id > 0 else 0,  # Инкрементальный поиск
                                hash=0
                            ))
                            
                            if search_results and hasattr(search_results, "messages"):
                                for msg in search_results.messages:
                                    if not hasattr(msg, "message") or not msg.message:
                                        continue
                                    messages_list.append(msg)
                                    
                                    # Отладочный режим
                                    if self.debug_mode and debug_count < self.debug_limit:
                                        debug_count += 1
                                        logger.debug(f"[DEBUG] Сообщение #{debug_count} из {channel.get('name')} (SearchRequest '{keyword}'): {msg.message[:100]}...")
                            
                            await asyncio.sleep(0.3)  # Антифлуд между запросами
                        except Exception as search_err:
                            logger.debug(f"⚠️ SearchRequest не удался для '{keyword}' в канале {cid}: {search_err}. Используем iter_messages.")
                            # Fallback на iter_messages если SearchRequest не работает
                            break
                    
                    # Если SearchRequest не дал результатов или упал, используем iter_messages как fallback
                    if not messages_list:
                        logger.debug(f"SearchRequest не дал результатов для {channel.get('name')}. Используем iter_messages.")
                        message_count = 0
                        async for message in client.iter_messages(cid, **iter_params):
                            if not message.text:
                                continue
                            messages_list.append(message)
                            message_count += 1
                            
                            # Умная задержка: каждые 20 сообщений делаем паузу 0.5 сек для избежания FloodWait
                            if message_count % 20 == 0:
                                await asyncio.sleep(0.5)
                            
                            # Отладочный режим
                            if self.debug_mode and debug_count < self.debug_limit:
                                debug_count += 1
                                logger.debug(f"[DEBUG] Сообщение #{debug_count} из {channel.get('name')}: {message.text[:100]}...")
                except Exception as search_fallback_error:
                    # Если SearchRequest полностью не работает, используем iter_messages
                    logger.debug(f"⚠️ SearchRequest недоступен для канала {cid}: {search_fallback_error}. Используем iter_messages.")
                    message_count = 0
                    async for message in client.iter_messages(cid, **iter_params):
                        if not message.text:
                            continue
                        messages_list.append(message)
                        message_count += 1
                        
                        # Умная задержка: каждые 20 сообщений делаем паузу 0.5 сек для избежания FloodWait
                        if message_count % 20 == 0:
                            await asyncio.sleep(0.5)
                        
                        # Отладочный режим
                        if self.debug_mode and debug_count < self.debug_limit:
                            debug_count += 1
                            logger.debug(f"[DEBUG] Сообщение #{debug_count} из {channel.get('name')}: {message.text[:100]}...")
                
                logger.info(f'📊 Канал {channel.get("name")}: проверено сообщений: {len(messages_list)}')
                self.total_scanned += len(messages_list)
                
                for message in messages_list:
                    # ── ФИЛЬТР: Пропускаем посты от самого канала (Admin/Channel ID) ─────────────
                    # Это спасает от превращения постов Юлии в лидов
                    sender_id = getattr(message, "sender_id", None)
                    peer_id = getattr(message, "peer_id", None)
                    
                    # Проверяем, является ли отправитель самим каналом
                    if sender_id and peer_id:
                        # Если sender_id совпадает с ID канала - это пост от канала, пропускаем
                        if hasattr(peer_id, "channel_id") and sender_id == peer_id.channel_id:
                            logger.debug(f"⏭️ Пропущен пост от канала (sender_id={sender_id} == channel_id={peer_id.channel_id})")
                            continue
                    
                    # Проверяем тип отправителя - нам нужны только User, не Channel
                    if message.sender:
                        from telethon.tl.types import User, Channel
                        if isinstance(message.sender, Channel):
                            logger.debug(f"⏭️ Пропущен пост от канала (тип: Channel, sender_id={sender_id})")
                            continue
                        if not isinstance(message.sender, User):
                            # Пропускаем ботов и другие типы
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
                    
                    # ── ПРОВЕРКА КЛЮЧЕВЫХ СЛОВ: если сообщение от пользователя содержит ключевые слова — это лид ──
                    # Проверяем наличие ключевых слов (для статистики)
                    has_keywords = any(kw.lower() in message.text.lower() for kw in self._load_keywords())
                    if has_keywords:
                        self.total_with_keywords += 1
                        if self.debug_mode:
                            logger.debug(f"[DEBUG] Сообщение с ключевыми словами: {message.text[:100]}...")
                    
                    if self.detect_lead(message.text):
                        # Дополнительная проверка: убеждаемся, что это не пост от канала
                        if sender_id and peer_id and hasattr(peer_id, "channel_id"):
                            if sender_id == peer_id.channel_id:
                                logger.debug(f"⏭️ Пропущен лид от канала (дополнительная проверка)")
                                continue
                        
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
                        self.total_leads += 1
                        logger.info(f"✅ Найден лид в канале {channel['name']}: {message.text[:80]}...")
                    elif self.debug_mode and has_keywords:
                        # В debug режиме логируем, почему сообщение с ключевыми словами не стало лидом
                        logger.debug(f"[DEBUG] Сообщение с ключевыми словами не прошло фильтр detect_lead(): {message.text[:100]}...")
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
                                # Проверенные источники из БД: используем короткий интервал (5 сек)
                                is_verified = channel.get("db_id") is not None
                                ent = await self._throttled_get_entity(client, cid, is_verified=is_verified)
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
                
                # ── Парсинг комментариев из Discussion Group ────────────────────
                if discussion_group_id:
                    try:
                        discussion_count = 0
                        discussion_scanned = 0
                        logger.info(f"💬 Парсинг комментариев из Discussion Group канала {channel.get('name')}...")
                        
                        # Собираем все сообщения для логирования
                        discussion_messages = []
                        message_count = 0
                        async for message in client.iter_messages(discussion_group_id, limit=tg_limit):
                            if not message.text:
                                continue
                            discussion_messages.append(message)
                            message_count += 1
                            
                            # Умная задержка: каждые 20 сообщений делаем паузу 0.5 сек для избежания FloodWait
                            if message_count % 20 == 0:
                                await asyncio.sleep(0.5)
                        
                        logger.info(f'Проверено сообщений в Discussion Group: {len(discussion_messages)}')
                        
                        for message in discussion_messages:
                            # ── ФИЛЬТР: Только сообщения от User, не от каналов ────────────────────
                            sender_id = getattr(message, "sender_id", None)
                            peer_id = getattr(message, "peer_id", None)
                            
                            # Проверяем, является ли отправитель самим каналом
                            if sender_id and peer_id:
                                if hasattr(peer_id, "channel_id") and sender_id == peer_id.channel_id:
                                    logger.debug(f"⏭️ Пропущен комментарий от канала в Discussion Group (sender_id={sender_id} == channel_id={peer_id.channel_id})")
                                    continue
                            
                            if message.sender:
                                from telethon.tl.types import User, Channel
                                if isinstance(message.sender, Channel):
                                    logger.debug(f"⏭️ Пропущен комментарий от канала в Discussion Group (тип: Channel)")
                                    continue
                                if not isinstance(message.sender, User):
                                    # Пропускаем ботов и другие типы
                                    continue
                            
                            discussion_scanned += 1
                            
                            # ── ПРОВЕРКА КЛЮЧЕВЫХ СЛОВ: если сообщение от пользователя содержит ключевые слова — это лид ──
                            # Проверяем, является ли сообщение комментарием к посту из основного канала
                            # (в Discussion Group сообщения могут быть связаны с постами через reply_to)
                            if self.detect_lead(message.text):
                                author_id = getattr(message, "sender_id", None)
                                author_name = None
                                if getattr(message, "sender", None):
                                    s = message.sender
                                    author_name = getattr(s, "username", None) or getattr(s, "first_name", None)
                                    if author_name and getattr(s, "last_name", None):
                                        author_name = f"{author_name} {s.last_name}".strip()
                                
                                # Формируем URL комментария
                                comment_url = self._tg_post_url(discussion_group_id, message.id)
                                
                                post = ScoutPost(
                                    source_type="telegram",
                                    source_name=f"{channel['name']} (комментарии)",
                                    source_id=str(discussion_group_id),
                                    post_id=str(message.id),
                                    text=message.text,
                                    author_id=author_id,
                                    author_name=author_name,
                                    url=comment_url,
                                    source_link=channel.get("link") or "",
                                    is_comment=True,  # Помечаем как комментарий
                                    original_channel_id=str(cid),
                                )
                                posts.append(post)
                                discussion_count += 1
                                logger.debug(f"💬 Найден лид в комментариях: {message.text[:50]}...")
                        
                        if discussion_count > 0:
                            logger.info(f"💬 Discovery: найдено {discussion_count} лидов в комментариях канала {channel.get('name')}")
                            self.last_scan_report.append({
                                "type": "telegram_discussion",
                                "name": f"{channel['name']} (комментарии)",
                                "id": discussion_group_id,
                                "status": "ok",
                                "posts": discussion_count,
                                "scanned": discussion_scanned,
                                "error": None,
                            })
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка парсинга Discussion Group канала {channel.get('name')}: {e}")
                        self.last_scan_report.append({
                            "type": "telegram_discussion",
                            "name": f"{channel['name']} (комментарии)",
                            "id": discussion_group_id,
                            "status": "error",
                            "posts": 0,
                            "scanned": 0,
                            "error": str(e),
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

        # Режим «Тишины»: перед проверкой новых ссылок — пауза 10 сек (для новых источников)
        if new_links_queue:
            logger.info("[SCOUT] Режим тишины: пауза 10 сек перед проверкой %s новых ссылок (Discovery).", len(new_links_queue))
            print("[SCOUT] Режим тишины: пауза 10 сек перед проверкой новых ссылок.", flush=True)
            await asyncio.sleep(10)
        # Обработка очереди: строго по одной с паузой 60 сек между запросами (anti-flood для новых источников)
        for url in new_links_queue:
            try:
                # Новые ссылки из Discovery: используем длинный интервал (60 сек)
                entity = await self._throttled_get_entity(client, url, is_verified=False)
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
                                # Новые ссылки из Discovery: используем длинный интервал (60 сек)
                                full = await self._throttled_get_entity(client, entity, is_verified=False)
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
            # resolve_telegram_link используется для новых ссылок (Discovery), используем длинный интервал
            await self._wait_get_entity_throttle(is_verified=False)
            entity = await client.get_entity(link)
            self._last_get_entity_at = time.monotonic()
            cid = getattr(entity, "id", None)
            title = getattr(entity, "title", None) or getattr(entity, "username", None) or (str(cid) if cid else link)
            participants = getattr(entity, "participants_count", None)
            if participants is None and isinstance(entity, (Channel, Chat)):
                try:
                    # Новые ссылки из Discovery: используем длинный интервал (60 сек)
                    await self._wait_get_entity_throttle(is_verified=False)
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
        """Выполнение запроса к VK API с обработкой ошибок.
        
        Returns:
            dict: Ответ от VK API или None в случае ошибки
        """
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
                        error_info = data["error"]
                        error_code = error_info.get("error_code", 0)
                        error_msg = error_info.get("error_msg", "Unknown error")
                        
                        # Специальная обработка ошибок доступа
                        if error_code in [15, 18, 30]:  # 15=Access denied, 18=Deleted/banned, 30=Private
                            logger.debug(f"⚠️ VK API access error (code {error_code}): {error_msg}")
                        else:
                            logger.error(f"❌ VK API error (code {error_code}): {error_msg}")
                        return None
                    return data.get("response")
        except Exception as e:
            logger.error(f"❌ VK request error: {e}")
            return None

    async def parse_vk(self, db=None) -> List[ScoutPost]:
        """
        Парсинг VK групп из БД target_resources (приоритет) или из .env (fallback).
        
        Ищет посты по ключевым словам, оставляет комментарии.
        
        Args:
            db: Опциональный объект БД для загрузки групп из target_resources
        
        Returns:
            List[ScoutPost]: Список найденных лидов
        """
        if not self.enabled:
            logger.info("🔍 Scout VK: выключен")
            return []
        
        if not self.vk_token:
            logger.error("❌ VK_TOKEN не настроен")
            return []
        
        # ── ЗАГРУЗКА ГРУПП ИЗ БД (ПРИОРИТЕТ) ──────────────────────────────────────
        vk_groups = await self._load_vk_groups(db=db)
        
        if not vk_groups:
            logger.warning("⚠️ VK группы не найдены ни в БД, ни в .env")
            return []
        
        logger.info(f"🔍 Сканирование {len(vk_groups)} VK групп из БД target_resources...")

        posts = []
        keywords = self._load_keywords()

        # Сколько постов брать для разбора комментариев (в комментариях чаще пишут «посоветуйте», «как узаконить»)
        # Используем глобальный SCAN_LIMIT из config.py для VK тоже
        from config import SCAN_LIMIT
        vk_posts_to_scan = int(os.getenv("SCOUT_VK_POSTS_FOR_COMMENTS", str(min(SCAN_LIMIT // 10, 20))))  # Адаптивно: до 20 постов
        vk_comments_per_post = int(os.getenv("SCOUT_VK_COMMENTS_PER_POST", str(min(SCAN_LIMIT // 3, 50))))  # Адаптивно: до 50 комментариев

        # ── ПРИОРИТЕТНЫЕ ЖК: Перемещаем в начало списка для приоритетной обработки ────
        priority_groups = [g for g in vk_groups if g.get("is_high_priority")]
        regular_groups = [g for g in vk_groups if not g.get("is_high_priority")]
        vk_groups = priority_groups + regular_groups
        
        if priority_groups:
            logger.info(f"⭐ Приоритетных ЖК найдено: {len(priority_groups)} (будут обработаны первыми)")
        
        for group in vk_groups:
            count = 0
            scanned_wall = 0
            scanned_comments = 0
            group_id = group["id"]
            group_name = group["name"]
            is_priority = group.get("is_high_priority", False)
            
            if is_priority:
                logger.info(f"⭐ Обработка ПРИОРИТЕТНОГО ЖК: {group_name} ({group_id})")
            
            try:
                # ── БЕЗОПАСНЫЙ ЗАПРОС: Обёртка try/except для приватных/забаненных групп ────
                from config import SCAN_LIMIT
                wall_posts = None
                
                try:
                    wall_posts = await self._vk_request("wall.get", {
                        "owner_id": -int(group_id),
                        "count": min(SCAN_LIMIT, 100),  # Максимум 100 постов (лимит VK API)
                        "extended": 0
                    })
                except Exception as api_error:
                    # Пропускаем приватные/забаненные группы без краша всего цикла
                    error_msg = str(api_error)
                    if "access denied" in error_msg.lower() or "private" in error_msg.lower() or "banned" in error_msg.lower():
                        logger.warning(f"⚠️ VK группа '{group_name}' ({group_id}): приватная/забаненная — пропущена")
                    else:
                        logger.warning(f"⚠️ VK группа '{group_name}' ({group_id}): ошибка API — {error_msg}")
                    
                    self.last_scan_report.append({
                        "type": "vk",
                        "name": group_name,
                        "id": group_id,
                        "status": "error",
                        "posts": 0,
                        "scanned": 0,
                        "error": f"API error: {error_msg[:100]}",
                    })
                    continue

                # Проверка на ошибки VK API (например, группа удалена или недоступна)
                if not wall_posts:
                    logger.warning(f"⚠️ VK группа '{group_name}' ({group_id}): wall.get вернул None — пропущена")
                    self.last_scan_report.append({
                        "type": "vk",
                        "name": group_name,
                        "id": group_id,
                        "status": "error",
                        "posts": 0,
                        "scanned": 0,
                        "error": "wall.get вернул None",
                    })
                    continue

                if "items" not in wall_posts:
                    logger.warning(f"⚠️ VK группа '{group_name}' ({group_id}): нет поля 'items' в ответе — пропущена")
                    self.last_scan_report.append({
                        "type": "vk",
                        "name": group_name,
                        "id": group_id,
                        "status": "ok",
                        "posts": 0,
                        "scanned": 0,
                        "error": None,
                    })
                    continue

                items = wall_posts["items"]
                scanned_wall = len(items)
                self.total_scanned += scanned_wall
                
                # ── ЛОГИРОВАНИЕ: "VK Scan: Processing [Group Name] ([ID]) - [N] new posts found" ────
                logger.info(f"📘 VK Scan: Processing {group_name} ({group_id}) - {scanned_wall} new posts found")

                # Посты на стене
                item_count = 0
                for item in items:
                    item_count += 1
                    text = item.get("text", "")
                    # Проверяем наличие ключевых слов (для статистики)
                    has_keywords = any(kw.lower() in text.lower() for kw in keywords) if text else False
                    if has_keywords:
                        self.total_with_keywords += 1
                        if self.debug_mode:
                            logger.debug(f"[DEBUG] VK пост с ключевыми словами: {text[:100]}...")
                    
                    # Умная задержка: каждые 20 постов делаем паузу 0.5 сек для избежания FloodWait
                    if item_count % 20 == 0:
                        await asyncio.sleep(0.5)
                    
                    # ── STOP_KEYWORDS: Фильтрация до отправки в ИИ ─────────────────────
                    text_lower = text.lower()
                    has_stop_keyword = any(stop_kw.lower() in text_lower for stop_kw in self.STOP_KEYWORDS)
                    if has_stop_keyword:
                        logger.debug(f"🚫 Пост отфильтрован по STOP_KEYWORD: {text[:50]}...")
                        continue
                    
                    if self.detect_lead(text):
                        # ── ПРИОРИТЕТНЫЙ ЖК: Добавляем маркер в source_name ────────────
                        source_name_display = group["name"]
                        if is_priority:
                            source_name_display = f"⭐ ПРИОРИТЕТНЫЙ ЖК: {group['name']}"
                        
                        post = ScoutPost(
                            source_type="vk",
                            source_name=source_name_display,
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
                        self.total_leads += 1
                        logger.info(f"✅ Найден лид в VK группе {group['name']}: {text[:80]}...")
                        await self.send_vk_comment(
                            item["id"], group["id"],
                            self.generate_outreach_message("vk", group["geo"])
                        )
                        if item.get("from_id"):
                            await self.send_vk_message(
                                item["from_id"],
                                self.generate_outreach_message("vk", group["geo"])
                            )

                # ── ПАРСИНГ КОММЕНТАРИЕВ ПОД ПОСТАМИ (wall.getComments) ────────────────
                # Комментарии к постам — там чаще пишут люди «посоветуйте мастера», «как узаконить»
                comment_posts = await self.parse_vk_comments(group, items[:vk_posts_to_scan], keywords, db)
                posts.extend(comment_posts)
                scanned_comments += len(comment_posts)
                count += len(comment_posts)
                
                # ── ПАРСИНГ ОБСУЖДЕНИЙ (board.getComments) ──────────────────────────────
                # Обсуждения (Discussions) — отдельные темы в группе, где люди задают вопросы
                board_posts = await self.parse_vk_boards(group, keywords, db)
                posts.extend(board_posts)
                scanned_comments += len(board_posts)
                count += len(board_posts)

                # Подсчитываем общее количество отсканированных элементов
                total_scanned_group = scanned_wall + scanned_comments
                
                # Добавляем маркер приоритета в отчет
                report_name = group_name
                if is_priority:
                    report_name = f"⭐ {group_name}"
                
                self.last_scan_report.append({
                    "type": "vk",
                    "name": report_name,
                    "id": group_id,
                    "status": "ok",
                    "posts": count,
                    "scanned": total_scanned_group,
                    "error": None,
                    "is_priority": is_priority,  # Маркер приоритета для отчетов
                })
                logger.info(f"📊 VK группа {group_name}: всего просмотрено {total_scanned_group} (посты: {scanned_wall}, комментарии: {scanned_comments}), найдено лидов: {count}")
                if count > 0 and db:
                    try:
                        await db.set_setting("scout_vk_lead_" + str(group["id"]), datetime.now().isoformat())
                    except Exception:
                        pass
            except Exception as e:
                # Безопасная обработка ошибок: логируем и продолжаем цикл
                error_msg = str(e)[:200]
                logger.error(f"❌ Ошибка группы {group_name} ({group_id}): {error_msg}")
                self.last_scan_report.append({
                    "type": "vk",
                    "name": group_name,
                    "id": group_id,
                    "status": "error",
                    "posts": 0,
                    "scanned": 0,
                    "error": error_msg,
                })
                # Продолжаем цикл — не падаем на одной группе
                continue
        
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

    async def parse_vk_comments(self, group: dict, wall_items: list, keywords: list, db=None) -> List[ScoutPost]:
        """
        Парсинг комментариев под постами VK (wall.getComments).
        
        Args:
            group: Словарь с данными группы (id, name, geo)
            wall_items: Список постов со стены для проверки комментариев
            keywords: Список ключевых слов для фильтрации
            db: Опциональный объект БД для проверки приоритетов
        
        Returns:
            List[ScoutPost]: Список найденных лидов из комментариев
        """
        posts = []
        from config import SCAN_LIMIT
        vk_comments_per_post = int(os.getenv("SCOUT_VK_COMMENTS_PER_POST", str(min(SCAN_LIMIT // 3, 50))))
        
        comment_post_count = 0
        for item in wall_items:
            comment_post_count += 1
            
            try:
                comments_data = await self._vk_request("wall.getComments", {
                    "owner_id": -int(group["id"]),
                    "post_id": item["id"],
                    "count": vk_comments_per_post,
                    "need_likes": 0,
                    "extended": 0,
                })
                
                if not comments_data or "items" not in comments_data:
                    continue
                
                # Обновляем счетчик просмотренных комментариев
                comments_items = comments_data.get("items", [])
                self.total_scanned += len(comments_items)
                
                comment_count = 0
                for comm in comments_items:
                    comment_count += 1
                    ctext = comm.get("text", "")
                    if not ctext:
                        continue
                    
                    # ── STOP_KEYWORDS: Фильтрация до отправки в ИИ ─────────────────────
                    text_lower = ctext.lower()
                    has_stop_keyword = any(stop_kw.lower() in text_lower for stop_kw in self.STOP_KEYWORDS)
                    if has_stop_keyword:
                        logger.debug(f"🚫 Комментарий отфильтрован по STOP_KEYWORD: {ctext[:50]}...")
                        continue
                    
                    # Проверяем наличие ключевых слов
                    has_keywords = any(kw.lower() in text_lower for kw in keywords)
                    if has_keywords:
                        self.total_with_keywords += 1
                    
                    # Умная задержка: каждые 20 комментариев делаем паузу 0.5 сек для избежания FloodWait
                    if comment_count % 20 == 0:
                        await asyncio.sleep(0.5)
                    
                    if not self.detect_lead(ctext):
                        continue
                    
                    # ── ПРИОРИТЕТНЫЙ ЖК: Добавляем маркер в source_name ────────────
                    is_priority = group.get("is_high_priority", False)
                    source_name_display = group["name"] + " (коммент)"
                    if is_priority:
                        source_name_display = f"⭐ ПРИОРИТЕТНЫЙ ЖК: {group['name']} (коммент)"
                    
                    post = ScoutPost(
                        source_type="vk",
                        source_name=source_name_display,
                        source_id=group["id"],
                        post_id=f"{item['id']}_c{comm.get('id', 0)}",
                        text=ctext,
                        author_id=comm.get("from_id"),
                        url=f"https://vk.com/wall-{group['id']}_{item['id']}?reply={comm.get('id', 0)}",
                        published_at=datetime.fromtimestamp(comm.get("date", 0)) if comm.get("date") else None,
                        likes=0,
                        comments=0,
                        is_comment=True,  # Помечаем как комментарий
                    )
                    posts.append(post)
                    self.total_leads += 1
                    logger.info(f"✅ Найден лид в комментариях VK группы {group['name']}: {ctext[:80]}...")
                    
                    if comm.get("from_id"):
                        await self.send_vk_message(
                            comm["from_id"],
                            self.generate_outreach_message("vk", group["geo"])
                        )
                
                # Умная задержка: каждые 5 постов с комментариями делаем паузу 0.5 сек
                if comment_post_count % 5 == 0:
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                logger.warning(f"⚠️ Ошибка парсинга комментариев к посту {item.get('id')}: {e}")
                continue
        
        return posts
    
    async def parse_vk_boards(self, group: dict, keywords: list, db=None) -> List[ScoutPost]:
        """
        Парсинг обсуждений VK (board.getComments для тем в разделе "Обсуждения").
        
        Args:
            group: Словарь с данными группы (id, name, geo)
            keywords: Список ключевых слов для фильтрации
            db: Опциональный объект БД для проверки приоритетов
        
        Returns:
            List[ScoutPost]: Список найденных лидов из обсуждений
        """
        posts = []
        from config import SCAN_LIMIT
        vk_topics_limit = int(os.getenv("SCOUT_VK_TOPICS_LIMIT", "50"))  # Последние 50 тем
        vk_comments_per_topic = int(os.getenv("SCOUT_VK_COMMENTS_PER_TOPIC", str(min(SCAN_LIMIT // 2, 30))))
        
        try:
            # Получаем список тем обсуждений (board.getTopics)
            topics_data = await self._vk_request("board.getTopics", {
                "group_id": group["id"],
                "count": vk_topics_limit,
                "order": 1,  # 1 = по дате обновления (новые первыми)
                "extended": 0,
            })
            
            if not topics_data or "items" not in topics_data:
                logger.debug(f"📋 VK группа {group['name']}: нет обсуждений или они недоступны")
                return posts
            
            topics = topics_data.get("items", [])
            logger.info(f"💬 VK группа {group['name']}: найдено {len(topics)} тем обсуждений")
            
            topic_count = 0
            for topic in topics:
                topic_count += 1
                topic_id = topic.get("id")
                if not topic_id:
                    continue
                
                try:
                    # Получаем комментарии к теме (board.getComments)
                    comments_data = await self._vk_request("board.getComments", {
                        "group_id": group["id"],
                        "topic_id": topic_id,
                        "count": vk_comments_per_topic,
                        "need_likes": 0,
                        "extended": 0,
                    })
                    
                    if not comments_data or "items" not in comments_data:
                        continue
                    
                    # Обновляем счетчик просмотренных комментариев из обсуждений
                    comments_items = comments_data.get("items", [])
                    self.total_scanned += len(comments_items)
                    
                    comment_count = 0
                    for comm in comments_items:
                        comment_count += 1
                        ctext = comm.get("text", "")
                        if not ctext:
                            continue
                        
                        # ── STOP_KEYWORDS: Фильтрация до отправки в ИИ ─────────────────────
                        text_lower = ctext.lower()
                        has_stop_keyword = any(stop_kw.lower() in text_lower for stop_kw in self.STOP_KEYWORDS)
                        if has_stop_keyword:
                            logger.debug(f"🚫 Комментарий из обсуждения отфильтрован по STOP_KEYWORD: {ctext[:50]}...")
                            continue
                        
                        # Проверяем наличие ключевых слов
                        has_keywords = any(kw.lower() in text_lower for kw in keywords)
                        if has_keywords:
                            self.total_with_keywords += 1
                        
                        # Умная задержка: каждые 20 комментариев делаем паузу 0.5 сек
                        if comment_count % 20 == 0:
                            await asyncio.sleep(0.5)
                        
                        if not self.detect_lead(ctext):
                            continue
                        
                        # ── ПРИОРИТЕТНЫЙ ЖК: Добавляем маркер в source_name ────────────
                        is_priority = group.get("is_high_priority", False)
                        source_name_display = group["name"] + " (обсуждение)"
                        if is_priority:
                            source_name_display = f"⭐ ПРИОРИТЕТНЫЙ ЖК: {group['name']} (обсуждение)"
                        
                        post = ScoutPost(
                            source_type="vk",
                            source_name=source_name_display,
                            source_id=group["id"],
                            post_id=f"topic{topic_id}_c{comm.get('id', 0)}",
                            text=ctext,
                            author_id=comm.get("from_id"),
                            url=f"https://vk.com/topic-{group['id']}_{topic_id}?post={comm.get('id', 0)}",
                            published_at=datetime.fromtimestamp(comm.get("date", 0)) if comm.get("date") else None,
                            likes=0,
                            comments=0,
                            is_comment=True,  # Помечаем как комментарий
                        )
                        posts.append(post)
                        self.total_leads += 1
                        logger.info(f"✅ Найден лид в обсуждении VK группы {group['name']}: {ctext[:80]}...")
                        
                        if comm.get("from_id"):
                            await self.send_vk_message(
                                comm["from_id"],
                                self.generate_outreach_message("vk", group["geo"])
                            )
                    
                    # Умная задержка: каждые 5 тем делаем паузу 0.5 сек
                    if topic_count % 5 == 0:
                        await asyncio.sleep(0.5)
                        
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка парсинга обсуждения {topic_id}: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"⚠️ Ошибка получения обсуждений для группы {group['name']}: {e}")
        
        return posts

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

    async def scan_all(self, db=None) -> List[ScoutPost]:
        """Полное сканирование всех источников. Заполняет last_scan_report.
        
        Args:
            db: Опциональный объект БД для загрузки ресурсов из target_resources
        """
        self.last_scan_report = []
        self.last_scan_at = datetime.now()
        # Сбрасываем статистику перед новым сканом
        self.total_scanned = 0
        self.total_with_keywords = 0
        self.total_leads = 0
        self.total_hot_leads = 0
        all_posts = []

        try:
            tg_posts = await self.parse_telegram(db=db)
            all_posts.extend(tg_posts)
        except Exception as e:
            logger.error(f"❌ TG scan error: {e}")

        try:
            vk_posts = await self.parse_vk(db=db)  # Передаём БД для загрузки VK групп из target_resources
            all_posts.extend(vk_posts)
        except Exception as e:
            logger.error(f"❌ VK scan error: {e}")

        return all_posts

    def get_last_scan_report(self) -> str:
        """Форматированный отчёт: где был шпион, сколько просмотрено, сколько лидов."""
        if not self.last_scan_report:
            return "📭 Отчёта ещё нет. Дождитесь следующего запуска охоты за лидами."
        lines = ["🕵️ <b>Отчёт шпиона</b> (последний скан)"]
        if self.last_scan_at:
            lines.append(f"⏱ {self.last_scan_at.strftime('%d.%m.%Y %H:%M')}\n")
        tg_ok = [r for r in self.last_scan_report if r["type"] == "telegram" and r["status"] == "ok"]
        tg_err = [r for r in self.last_scan_report if r["type"] == "telegram" and r["status"] == "error"]
        vk_ok = [r for r in self.last_scan_report if r["type"] == "vk" and r["status"] == "ok"]
        vk_err = [r for r in self.last_scan_report if r["type"] == "vk" and r["status"] == "error"]
        total_scanned = sum(r.get("scanned", 0) for r in tg_ok + vk_ok)
        total_leads = sum(r.get("posts", 0) for r in tg_ok + vk_ok)
        
        # Используем статистику из self, если она есть
        if self.total_scanned > 0:
            total_scanned = self.total_scanned
        if self.total_with_keywords > 0:
            lines.append(f"📊 <b>Всего просмотрено:</b> {total_scanned} сообщений")
            lines.append(f"🔍 <b>С ключевыми словами:</b> {self.total_with_keywords}")
            lines.append(f"🎯 <b>Найдено лидов:</b> {total_leads}\n")
        else:
            lines.append(f"📊 Просмотрено сообщений/постов: <b>{total_scanned}</b>, найдено лидов: <b>{total_leads}</b>\n")
        
        if tg_ok or tg_err:
            lines.append("<b>📱 Telegram каналы:</b>")
            for r in tg_ok:
                s = f"  ✅ {r['name']} — {r['posts']} лидов"
                if r.get("scanned") is not None and r.get("scanned") > 0:
                    s += f" (просмотрено {r['scanned']})"
                lines.append(s)
            for r in tg_err:
                lines.append(f"  ❌ {r['name']} — {r.get('error', 'ошибка')}")
        if vk_ok or vk_err:
            lines.append("<b>📘 VK группы:</b>")
            for r in vk_ok:
                s = f"  ✅ {r['name']} — {r['posts']} лидов"
                if r.get("scanned") is not None and r.get("scanned") > 0:
                    s += f" (просмотрено {r['scanned']})"
                lines.append(s)
            for r in vk_err:
                lines.append(f"  ❌ {r['name']} — {r.get('error', 'ошибка')}")
        if total_scanned == 0:
            lines.append("\n⚠️ <b>ВНИМАНИЕ:</b> Просмотрено 0 сообщений. Проверьте:")
            lines.append("  • Есть ли активные источники в БД (target_resources, status='active')")
            lines.append("  • Правильно ли настроены SCOUT_TG_CHANNELS / SCOUT_VK_GROUPS в .env")
            lines.append("  • Авторизован ли Telethon (файл anton_parser.session)")
        elif total_scanned > 0 and total_leads == 0:
            lines.append("\n💡 Если лидов 0 при большом объёме — проверьте ключевые слова и фильтры")
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