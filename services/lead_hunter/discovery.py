import logging
import os
import asyncio
import aiohttp
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# =============================================================================
# СТОП-СЛОВА (Pre-filter): Жесткая фильтрация до отправки в AI
# =============================================================================
# Если текст содержит любое из этих слов, пост игнорируется без траты токенов
# =============================================================================

# Категория «Образование и Наука»
STOP_WORDS_EDUCATION = [
    "студент", "кафедра", "доцент", "преподаватель", "лекция", "учебный",
    "диссертация", "БГИТУ", "вуз", "колледж", "аспирант", "экзамен",
    "занятие", "наука", "университет", "институт", "академия"
]

# Категория «Экспертный спам»
STOP_WORDS_EXPERT_SPAM = [
    "подписывайтесь", "наш канал", "заказать услугу", "статья",
    "рассказываем в видео", "чек-лист", "бесплатный гайд",
    "обучение перепланировкам", "курс", "вебинар", "мастер-класс"
]

# Категория «Общий шум»
STOP_WORDS_GENERAL = [
    "вакансия", "требуется", "сдам квартиру", "продам машину",
    "поздравляем с днем", "памятная дата", "юбилей", "торжество"
]

# Объединенный список всех стоп-слов
STOP_WORDS_ALL = STOP_WORDS_EDUCATION + STOP_WORDS_EXPERT_SPAM + STOP_WORDS_GENERAL

# =============================================================================
# РАСШИРЕННЫЕ КЛЮЧЕВЫЕ СЛОВА ДЛЯ ГЛОБАЛЬНОГО ПОИСКА
# =============================================================================
# Discovery комбинирует эти слова с районами Москвы для поиска сотен чатов
# Гео-фильтрация (Москва/МО) применяется позже на этапе анализа постов
# =============================================================================

# Общие запросы (комбинируются с районами)
GENERAL_KEYWORDS = [
    "перепланировка москва",
    "согласование перепланировки",
    "БТИ москва чат",
    "дизайн интерьера чат",
    "ремонт квартир мск",
]

# Географические запросы (чаты жильцов)
GEO_KEYWORDS = [
    "ЖК Москва чат",
    "соседи ЖК",
    "новостройки москва обсуждение",
    "чат жильцов",
]

# Районы Москвы для комбинирования
MOSCOW_DISTRICTS = [
    "ЮВАО", "ЮАО", "ЮЗАО",
    "СВАО", "САО", "СЗАО",
    "ВАО", "ЦАО", "ЗАО",
    "НАО", "ТАО",  # Новая Москва
]

# Базовые ключевые слова (без комбинирования)
BASE_KEYWORDS = [
    "перепланировка",
    "согласование перепланировки",
    "узаконить перепланировку",
    "ремонт квартиры",
    "перепланировка квартиры",
    "согласование МЖИ",
    "проект перепланировки",
    "Москва",
    "Московская область",
    "МО",
    "ЖК Москва",
    "новостройки Москвы",
]

# Итоговый список ключевых слов (генерируется динамически)
DEFAULT_KEYWORDS = BASE_KEYWORDS.copy()

# Пул открытых каналов для «Глобального поиска».
# Discovery использует их как отправную точку для поиска.
# ВАЖНО: Discovery автоматически находит новые каналы по ключевым словам,
# этот список — только рабочие каналы для начального сканирования.
OPEN_HUNT_SOURCES = [
    # ── Недвижимость и новостройки (только рабочие) ────────────────────────
    {"link": "https://t.me/novostroyki_moscow",     "title": "Новостройки Москвы",               "participants_count": 4500},
    {"link": "https://t.me/realtymoscow",           "title": "Риелторы Москвы",                  "participants_count": 0},
    # ── Ремонт и перепланировки (только рабочие) ────────────────────────────
    {"link": "https://t.me/pereplanirovka_msk",     "title": "Перепланировки Москва",             "participants_count": 0},
    {"link": "https://t.me/remont_kvartir_moskva",  "title": "Ремонт квартир Москва",             "participants_count": 0},
    {"link": "https://t.me/stroitelstvo_remont",    "title": "Строительство и ремонт",            "participants_count": 0},
]


class Discovery:
    """Автопоиск новых каналов и групп для мониторинга.

    Стратегия «Глобальный поиск»:
    - Ищет каналы по ключевым словам (перепланировка, ремонт, Москва)
    - Не привязан к конкретным ЖК
    - Гео-фильтрация (Москва/МО) применяется на этапе анализа постов
    
    При инициализации берёт ключевые слова из SCOUT_KEYWORDS (env, через запятую).
    Если переменная не задана — используется DEFAULT_KEYWORDS.
    """

    def __init__(self):
        """Инициализация Discovery с расширенными ключевыми словами.
        
        Генерирует комбинации ключевых слов с районами Москвы для поиска сотен чатов.
        
        ВАЖНО: Если SCOUT_KEYWORDS задано в .env, но содержит менее 5 ключевых слов,
        используется расширенный список вместо env (чтобы избежать ситуации с одним словом).
        """
        env = os.getenv("SCOUT_KEYWORDS", "").strip()
        if env:
            env_keywords = [k.strip() for k in env.split(",") if k.strip()]
            # Если в env задано слишком мало ключевых слов (< 5) - игнорируем и используем расширенный список
            if len(env_keywords) < 5:
                logger.warning(
                    f"⚠️ SCOUT_KEYWORDS содержит только {len(env_keywords)} слово(а): {env_keywords}. "
                    f"Используется расширенный список ключевых слов вместо env."
                )
                self.keywords = self._generate_expanded_keywords()
            else:
                # Если достаточно слов - используем из env
                self.keywords = env_keywords
                logger.info(f"✅ Используются ключевые слова из SCOUT_KEYWORDS: {len(env_keywords)} слов")
        else:
            # Генерируем расширенный список с комбинациями
            self.keywords = self._generate_expanded_keywords()
            logger.info(f"✅ Используется расширенный список ключевых слов: {len(self.keywords)} слов")

    def _generate_expanded_keywords(self) -> List[str]:
        """Генерирует расширенный список ключевых слов с комбинациями районов."""
        expanded = BASE_KEYWORDS.copy()
        
        # Комбинируем общие запросы с районами
        for keyword in GENERAL_KEYWORDS:
            expanded.append(keyword)
            for district in MOSCOW_DISTRICTS:
                # Добавляем варианты: "перепланировка москва ЮВАО", "ЮВАО перепланировка москва"
                expanded.append(f"{keyword} {district}")
                expanded.append(f"{district} {keyword}")
        
        # Комбинируем географические запросы с районами
        for keyword in GEO_KEYWORDS:
            expanded.append(keyword)
            for district in MOSCOW_DISTRICTS:
                expanded.append(f"{keyword} {district}")
                expanded.append(f"{district} {keyword}")
        
        # Добавляем простые комбинации районов с базовыми словами
        for district in MOSCOW_DISTRICTS:
            expanded.append(f"ЖК {district}")
            expanded.append(f"чат {district}")
            expanded.append(f"{district} чат")
            expanded.append(f"соседи {district}")
        
        # Убираем дубликаты и возвращаем
        return list(dict.fromkeys(expanded))  # Сохраняет порядок, убирает дубликаты

    def get_keywords(self) -> List[str]:
        return self.keywords

    async def global_telegram_search(self, keywords: List[str] = None) -> List[Dict]:
        """Глобальный поиск Telegram каналов через Telethon API.
        
        Использует ключевые слова для поиска открытых каналов и групп.
        Возвращает список каналов для добавления в БД.
        
        Args:
            keywords: Список ключевых слов для поиска. Если не указан, используется self.keywords.
        
        Returns:
            Список словарей с полями: link, title, type='telegram', participants_count
        """
        from telethon import TelegramClient
        from telethon.tl.types import Channel, Chat
        from telethon.tl.functions.messages import SearchGlobalRequest
        from telethon.tl.types import InputMessagesFilterEmpty
        from config import API_ID, API_HASH
        
        kws = keywords or self.keywords[:10]  # Ограничиваем до 10 запросов за раз
        found_channels = []
        
        # Ключевые слова для поиска (из ТЗ)
        search_keywords = [
            "перепланировка",
            "акт МЖИ",
            "согласование",
            "штраф",
            "перепланировка москва",
            "согласование перепланировки",
            "БТИ москва",
        ]
        
        # Объединяем с переданными ключевыми словами
        search_keywords.extend([kw for kw in kws if kw not in search_keywords])
        search_keywords = search_keywords[:10]  # Максимум 10 запросов
        
        # ── ИСПРАВЛЕНИЕ: Используем тот же session name, что и в scout_parser ──────
        # Это позволяет использовать существующий файл сессии 'anton_parser.session'
        # вместо создания нового клиента, который не видит сессию
        client = TelegramClient('anton_parser', API_ID, API_HASH)
        
        try:
            await client.connect()
            if not await client.is_user_authorized():
                logger.warning("⚠️ Telethon не авторизован (файл сессии 'anton_parser.session' не найден или устарел)")
                logger.info("💡 Убедитесь, что scout_parser.py успешно авторизован в Telethon")
                return []
            
            for keyword in search_keywords:
                try:
                    # Глобальный поиск по ключевому слову
                    results = None
                    try:
                        results = await client(SearchGlobalRequest(
                            q=keyword,
                            filter=InputMessagesFilterEmpty(),
                            min_date=None,
                            max_date=None,
                            offset_rate=0,
                            offset_peer=None,
                            offset_id=0,
                            limit=20  # Максимум 20 результатов на запрос
                        ))
                    except TypeError as te:
                        # Обработка ошибки "Cannot cast NoneType"
                        if "NoneType" in str(te) or "cast" in str(te).lower():
                            logger.debug(f"⚠️ Ошибка типа при поиске '{keyword}': {te}. Переходим к следующему ключевому слову.")
                            continue
                        raise
                    except Exception as search_error:
                        # Другие ошибки поиска - логируем и продолжаем
                        logger.debug(f"⚠️ Ошибка поиска для '{keyword}': {search_error}. Переходим к следующему ключевому слову.")
                        continue
                    
                    # ── ИСПРАВЛЕНИЕ: Итерируемся напрямую по search_result.chats ────────
                    # Исключаем get_entity для каждого чата - используем данные из results.chats
                    if results is None:
                        logger.debug(f"Пустой результат поиска для '{keyword}' - переходим к следующему")
                        continue
                    
                    if not hasattr(results, "chats") or results.chats is None:
                        logger.debug(f"Нет атрибута chats в результатах для '{keyword}' - переходим к следующему")
                        continue
                    
                    seen_channels = set()
                    for chat in results.chats:
                        if chat is None:
                            continue
                        
                        # Проверяем наличие необходимых атрибутов
                        if not hasattr(chat, "id"):
                            continue
                        
                        chat_id = chat.id
                        if chat_id in seen_channels:
                            continue
                        seen_channels.add(chat_id)
                        
                        # Проверяем, что это канал (Channel) или группа (Chat)
                        if not isinstance(chat, (Channel, Chat)):
                            continue
                        
                        # Для каналов проверяем, что они публичные
                        if isinstance(chat, Channel):
                            if not hasattr(chat, "access_hash") or chat.access_hash is None:
                                continue  # Пропускаем приватные каналы
                            
                            username = getattr(chat, "username", None)
                            if username:
                                link = f"https://t.me/{username}"
                            else:
                                link = f"https://t.me/c/{abs(chat_id)}"
                            
                            title = getattr(chat, "title", "") or (username if username else f"Channel {chat_id}")
                            participants_count = getattr(chat, "participants_count", 0)
                            
                            # Проверяем на дубликаты
                            if not any(c.get("link") == link for c in found_channels):
                                found_channels.append({
                                    "link": link,
                                    "title": title,
                                    "type": "telegram",
                                    "participants_count": participants_count,
                                    "geo_tag": "Москва/МО",
                                })
                        elif isinstance(chat, Chat):
                            # Для групп используем ID
                            link = f"https://t.me/c/{abs(chat_id)}"
                            title = getattr(chat, "title", "") or f"Chat {chat_id}"
                            participants_count = getattr(chat, "participants_count", 0)
                            
                            if not any(c.get("link") == link for c in found_channels):
                                found_channels.append({
                                    "link": link,
                                    "title": title,
                                    "type": "telegram",
                                    "participants_count": participants_count,
                                    "geo_tag": "Москва/МО",
                                })
                    
                    # Небольшая задержка между запросами (антифлуд)
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка при поиске по ключевому слову '{keyword}': {e}")
                    continue
            
        except Exception as e:
            logger.error(f"❌ Ошибка при подключении к Telethon для global_telegram_search: {e}")
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        
        logger.info(f"🔍 Global Telegram Search: найдено {len(found_channels)} новых каналов")
        
        # ── ДОПОЛНИТЕЛЬНЫЙ ПОИСК: Если найдено 0 каналов, ищем в сообщениях ────────
        if len(found_channels) == 0:
            logger.info("🔍 Найдено 0 каналов через глобальный поиск. Пробуем поиск в сообщениях по ключевым словам...")
            message_channels = await self._search_channels_in_messages(search_keywords[:5])  # Ограничиваем до 5 запросов
            if message_channels:
                logger.info(f"✅ Поиск в сообщениях: найдено {len(message_channels)} каналов")
                found_channels.extend(message_channels)
        
        return found_channels

    async def _search_channels_in_messages(self, keywords: List[str]) -> List[Dict]:
        """Поиск ссылок на открытые чаты внутри сообщений других групп по ключевым словам.
        
        Это позволяет находить ссылки на открытые чаты, которые упоминаются в других группах.
        
        Args:
            keywords: Список ключевых слов для поиска в сообщениях.
        
        Returns:
            Список словарей с полями: link, title, type='telegram', participants_count
        """
        from telethon import TelegramClient
        from telethon.tl.functions.messages import SearchRequest
        from telethon.tl.types import MessageEntityUrl, MessageEntityTextUrl
        from telethon.tl.types import Channel, Chat
        from config import API_ID, API_HASH
        import re
        
        found_channels = []
        client = TelegramClient('anton_parser', API_ID, API_HASH)
        
        try:
            await client.connect()
            if not await client.is_user_authorized():
                logger.warning("⚠️ Telethon не авторизован для поиска в сообщениях")
                return []
            
            # Используем известные открытые каналы как отправную точку для поиска
            known_channels = [
                "novostroyki_moscow",
                "realtymoscow",
                "pereplanirovka_msk",
                "remont_kvartir_moskva",
            ]
            
            for channel_username in known_channels:
                try:
                    entity = await client.get_entity(channel_username)
                    if not isinstance(entity, Channel):
                        continue
                    
                    # Ищем сообщения с ключевыми словами в этом канале
                    for keyword in keywords[:3]:  # Ограничиваем до 3 ключевых слов на канал
                        try:
                            messages = await client(SearchRequest(
                                peer=entity,
                                q=keyword,
                                filter=None,
                                min_date=None,
                                max_date=None,
                                offset_id=0,
                                add_offset=0,
                                limit=10,  # Максимум 10 сообщений на запрос
                                max_id=0,
                                min_id=0,
                                hash=0
                            ))
                            
                            if not messages or not hasattr(messages, "messages"):
                                continue
                            
                            # Извлекаем ссылки на каналы из сообщений
                            for msg in messages.messages:
                                if not hasattr(msg, "message"):
                                    continue
                                
                                text = msg.message or ""
                                
                                # Ищем ссылки t.me/ в тексте
                                telegram_links = re.findall(r't\.me/([a-zA-Z0-9_]+)', text)
                                
                                for link_username in telegram_links:
                                    if link_username in known_channels:
                                        continue  # Пропускаем уже известные каналы
                                    
                                    try:
                                        # Пробуем получить информацию о канале по ссылке
                                        link_entity = await client.get_entity(f"t.me/{link_username}")
                                        
                                        if isinstance(link_entity, Channel):
                                            if hasattr(link_entity, "access_hash") and link_entity.access_hash:
                                                username = getattr(link_entity, "username", None)
                                                if username:
                                                    link = f"https://t.me/{username}"
                                                    title = getattr(link_entity, "title", "") or username
                                                    participants_count = getattr(link_entity, "participants_count", 0)
                                                    
                                                    # Проверяем на дубликаты
                                                    if not any(c.get("link") == link for c in found_channels):
                                                        found_channels.append({
                                                            "link": link,
                                                            "title": title,
                                                            "type": "telegram",
                                                            "participants_count": participants_count,
                                                            "geo_tag": "Москва/МО",
                                                        })
                                                        logger.debug(f"✅ Найден канал через поиск в сообщениях: {link}")
                                    except Exception as link_error:
                                        # Игнорируем ошибки получения канала (приватный, не существует и т.д.)
                                        logger.debug(f"⚠️ Не удалось получить канал t.me/{link_username}: {link_error}")
                                        continue
                            
                            await asyncio.sleep(0.5)  # Антифлуд
                        except Exception as search_error:
                            logger.debug(f"⚠️ Ошибка поиска в сообщениях канала {channel_username} по '{keyword}': {search_error}")
                            continue
                    
                    await asyncio.sleep(1)  # Задержка между каналами
                except Exception as channel_error:
                    logger.debug(f"⚠️ Ошибка доступа к каналу {channel_username}: {channel_error}")
                    continue
            
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при поиске каналов в сообщениях: {e}")
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        
        return found_channels

    async def find_new_sources(self, keywords: List[str] = None) -> List[Dict]:
        """Поиск новых источников по ключевым словам (глобальный поиск).

        Возвращает список открытых Telegram-каналов для добавления в БД.
        
        Логика:
          1. Использует global_telegram_search для реального поиска через Telegram API.
          2. Если ничего не найдено, фильтруем OPEN_HUNT_SOURCES по совпадению ключевых слов.
          3. Включаем все источники, где упомянута Москва/МО или тематика перепланировок.
        
        Гео-фильтрация (только Москва/МО) применяется позже на этапе анализа постов.
        """
        kws = keywords or self.keywords
        
        # ── РЕАЛЬНЫЙ ПОИСК ЧЕРЕЗ TELEGRAM API ────────────────────────────────────────
        try:
            global_results = await self.global_telegram_search(kws)
            if global_results:
                logger.info(f"✅ Global Telegram Search: найдено {len(global_results)} каналов через API")
                return global_results
        except Exception as e:
            logger.warning(f"⚠️ Global Telegram Search не удался: {e}. Используем fallback.")
        
        # Логируем только первые 10 ключевых слов для читаемости
        kws_preview = kws[:10]
        if len(kws) > 10:
            logger.info("🔍 Discovery: глобальный поиск каналов по ключевым словам (%d всего): %s...", 
                       len(kws), kws_preview)
        else:
            logger.info("🔍 Discovery: глобальный поиск каналов по ключевым словам: %s", kws_preview)

        # Гео-маркеры для фильтрации
        geo_markers = ["москва", "московск", "мск", "мкд", "новостройки", "ювао", "юао", "юзао", 
                      "свао", "сао", "сзао", "вао", "цао", "зао", "нао", "тао"]
        lower_kws = [k.lower() for k in kws]

        found = []
        for s in OPEN_HUNT_SOURCES:
            title_lower = (s.get("title") or "").lower()
            link_lower = (s.get("link") or "").lower()

            # Включаем, если совпадает с ключевым словом ИЛИ упомянута Москва/МО/район
            keyword_match = any(k in title_lower or k in link_lower for k in lower_kws)
            geo_match = any(marker in title_lower or marker in link_lower for marker in geo_markers)

            if keyword_match or geo_match:
                found.append(s)

        # Если ничего не найдено — возвращаем весь пул (рабочие каналы)
        result = found if found else OPEN_HUNT_SOURCES
        logger.info("🔍 Discovery: найдено источников для мониторинга: %d", len(result))
        return result
    
    async def scout_vk_resources(self, keywords: List[str] = None) -> List[Dict]:
        """Поиск новых VK групп по ключевым словам через VK API.
        
        Использует метод groups.search для поиска открытых групп ВКонтакте.
        Требуется VK_USER_TOKEN (токен пользователя), так как groups.search требует пользовательский доступ.
        
        Args:
            keywords: Список ключевых слов для поиска. Если не указан, используется self.keywords.
        
        Returns:
            Список словарей с полями: link, title, type='vk', participants_count
        """
        # ── ИСПРАВЛЕНИЕ: Используем VK_USER_TOKEN для groups.search ────────────────
        # groups.search требует пользовательский токен, не токен группы
        vk_token = os.getenv("VK_USER_TOKEN") or os.getenv("VK_TOKEN")
        if not vk_token:
            logger.warning("⚠️ VK_USER_TOKEN не настроен в .env, пропускаю поиск VK групп")
            logger.info("💡 Для поиска VK групп через groups.search требуется VK_USER_TOKEN (токен пользователя)")
            return []
        
        # Проверяем, что используется пользовательский токен
        if os.getenv("VK_USER_TOKEN"):
            logger.debug("✅ Используется VK_USER_TOKEN для поиска VK групп")
        elif os.getenv("VK_TOKEN"):
            logger.warning("⚠️ Используется VK_TOKEN вместо VK_USER_TOKEN. groups.search может не работать с токеном группы.")
        
        kws = keywords or self.keywords[:10]  # Ограничиваем до 10 запросов за раз
        vk_api_version = "5.199"
        found_groups = []
        
        async with aiohttp.ClientSession() as session:
            for keyword in kws:
                try:
                    # Поиск групп по ключевому слову
                    params = {
                        "q": keyword,
                        "type": "group",  # Только группы, не страницы
                        "count": 20,  # Максимум 20 групп на запрос
                        "access_token": vk_token,
                        "v": vk_api_version,
                    }
                    
                    async with session.get(
                        "https://api.vk.com/method/groups.search",
                        params=params,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        # ── ОБРАБОТКА ПУСТЫХ ОТВЕТОВ И ИСКЛЮЧЕНИЙ ──────────────────────────
                        if resp.status != 200:
                            logger.error(f"❌ VK API HTTP error {resp.status} при поиске '{keyword}'")
                            continue
                        
                        try:
                            data = await resp.json()
                        except Exception as json_error:
                            logger.error(f"❌ Ошибка парсинга JSON ответа VK API для '{keyword}': {json_error}")
                            continue
                        
                        if not data:
                            logger.warning(f"⚠️ Пустой ответ от VK API для '{keyword}'")
                            continue
                        
                        if "error" in data:
                            error_code = data['error'].get('error_code', 0)
                            error_msg = data['error'].get('error_msg', '')
                            
                            # ── ОБРАБОТКА ОШИБКИ 27 (требуется пользовательский токен) ────────
                            if error_code == 27:
                                logger.error("=" * 60)
                                logger.error(f"❌ VK API Error 27 при поиске '{keyword}': {error_msg}")
                                logger.error("")
                                logger.error("💡 ИНСТРУКЦИЯ: Для groups.search требуется VK_USER_TOKEN (токен пользователя)")
                                logger.error("")
                                logger.error("Проверьте:")
                                logger.error("  1. VK_USER_TOKEN установлен в .env (не VK_TOKEN группы)")
                                logger.error("  2. Токен пользователя получен через https://oauth.vk.com/authorize")
                                logger.error("  3. Токен имеет права: groups (доступ к группам)")
                                logger.error("=" * 60)
                                # Прерываем цикл, так как все запросы будут падать с той же ошибкой
                                break
                            
                            logger.error(f"❌ VK API error при поиске '{keyword}': код {error_code}, {error_msg}")
                            continue
                        
                        response = data.get("response")
                        if not response:
                            logger.warning(f"⚠️ Пустой response от VK API для '{keyword}'")
                            continue
                        
                        items = response.get("items", [])
                        if not items:
                            logger.debug(f"Нет результатов поиска для '{keyword}'")
                            continue
                        
                        for group in items:
                            # Фильтруем только открытые группы (is_closed == 0)
                            if group.get("is_closed", 1) == 0:
                                screen_name = group.get("screen_name", "")
                                group_id = group.get("id", 0)
                                
                                if screen_name:
                                    link = f"https://vk.com/{screen_name}"
                                elif group_id:
                                    link = f"https://vk.com/club{group_id}"
                                else:
                                    continue
                                
                                # Проверяем, что группа не дублируется
                                if not any(g.get("link") == link for g in found_groups):
                                    found_groups.append({
                                        "link": link,
                                        "title": group.get("name", ""),
                                        "type": "vk",
                                        "participants_count": group.get("members_count", 0),
                                        "geo_tag": "Москва/МО",  # По умолчанию, можно уточнить позже
                                    })
                        
                        # Небольшая задержка между запросами (антифлуд)
                        await asyncio.sleep(0.5)
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка при поиске VK групп по ключевому слову '{keyword}': {e}")
                    continue
        
        logger.info(f"🔍 Discovery VK: найдено {len(found_groups)} новых групп ВКонтакте")
        return found_groups
