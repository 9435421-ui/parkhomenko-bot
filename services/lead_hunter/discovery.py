import logging
import os
import asyncio
import aiohttp
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

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
        
        client = TelegramClient('discovery_client', API_ID, API_HASH)
        
        try:
            await client.connect()
            if not await client.is_user_authorized():
                logger.warning("⚠️ Telethon не авторизован, пропускаю global_telegram_search")
                return []
            
            for keyword in search_keywords:
                try:
                    # Глобальный поиск по ключевому слову
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
                    
                    # Извлекаем уникальные каналы из результатов
                    seen_channels = set()
                    for msg in results.messages:
                        if hasattr(msg, "peer_id") and hasattr(msg.peer_id, "channel_id"):
                            channel_id = msg.peer_id.channel_id
                            if channel_id in seen_channels:
                                continue
                            seen_channels.add(channel_id)
                            
                            try:
                                entity = await client.get_entity(channel_id)
                                if isinstance(entity, (Channel, Chat)):
                                    # Проверяем, что канал публичный
                                    if isinstance(entity, Channel) and entity.access_hash:
                                        username = getattr(entity, "username", None)
                                        if username:
                                            link = f"https://t.me/{username}"
                                        else:
                                            link = f"https://t.me/c/{abs(channel_id)}"
                                        
                                        # Проверяем на дубликаты
                                        if not any(c.get("link") == link for c in found_channels):
                                            found_channels.append({
                                                "link": link,
                                                "title": getattr(entity, "title", ""),
                                                "type": "telegram",
                                                "participants_count": getattr(entity, "participants_count", 0),
                                                "geo_tag": "Москва/МО",
                                            })
                            except Exception as e:
                                logger.debug(f"Ошибка при обработке канала {channel_id}: {e}")
                    
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
        Возвращает список групп для добавления в БД как target_resources.
        
        Args:
            keywords: Список ключевых слов для поиска. Если не указан, используется self.keywords.
        
        Returns:
            Список словарей с полями: link, title, type='vk', participants_count
        """
        vk_token = os.getenv("VK_TOKEN") or os.getenv("VK_USER_TOKEN")
        if not vk_token:
            logger.warning("⚠️ VK_TOKEN не настроен в .env, пропускаю поиск VK групп")
            return []
        
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
                        params=params
                    ) as resp:
                        data = await resp.json()
                        
                        if "error" in data:
                            logger.error(f"❌ VK API error при поиске '{keyword}': {data['error']}")
                            continue
                        
                        response = data.get("response", {})
                        items = response.get("items", [])
                        
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
