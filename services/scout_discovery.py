"""
services/scout_discovery.py — модуль автоматического поиска новых групп VK по ключевым словам и ГЕО.

Функционал:
  - Поиск групп VK по ключевым словам: "Москва", "ЖК", "Новоселы", "Перепланировка"
  - Фильтрация по типу (открытые группы, не реклама)
  - Автоматическое добавление новых групп в SCOUT_VK_GROUPS
  - Интеграция с vk_spy.py для автономной работы
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Set

import aiohttp

logger = logging.getLogger("ScoutDiscovery")

# Конфигурация
VK_TOKEN = os.getenv("VK_TOKEN", "")
VK_API = "5.199"

# Ключевые слова для поиска групп
SEARCH_KEYWORDS = [
    "Москва перепланировка",
    "ЖК перепланировка",
    "Новоселы перепланировка",
    "Москва перепланировка квартир",
    "ЖК Москва перепланировка",
    "Новоселы Москва",
    "перепланировка Москва",
    "перепланировка ЖК",
    "перепланировка новостройки",
    "перепланировка квартиры Москва",
]

# Фильтры для групп
MIN_MEMBERS = 100          # минимум участников
MAX_MEMBERS = 50000        # максимум участников (чтобы не попасть в огромные рекламные)
STOP_WORDS = [
    "реклама", "объявление", "услуги", "строительство", "ремонт", "дизайн",
    "интерьер", "мебель", "двери", "окна", "сантехника", "электрика",
    "обои", "ламинат", "плитка", "недвижимость", "агентство", "риелтор",
    "строительная", "компания", "торговля", "магазин", "продажа", "услуги",
    "монтаж", "установка", "демонтаж", "ремонт", "обслуживание", "продажи",
    "торг", "дилер", "поставка", "производство", "фабрика", "завод",
    "опт", "розница", "доставка", "монтаж", "установка", "обслуживание",
    "гарантия", "сервис", "ремонт", "обслуживание", "монтаж", "установка",
]

# Файл для хранения найденных групп
FOUND_GROUPS_FILE = Path("vk_scout_found_groups.json")
SEEN_GROUPS_FILE = Path("vk_scout_seen_groups.json")

# Интервал поиска новых групп (раз в сутки)
DISCOVERY_INTERVAL = 24 * 3600  # 24 часа


class ScoutDiscovery:
    """Модуль автоматического поиска новых групп VK по ключевым словам и ГЕО."""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.found_groups: Dict[str, Dict] = {}  # group_id -> info
        self.seen_groups: Set[str] = set()
        self.load_state()
    
    def load_state(self):
        """Загружает сохранённые группы и просмотренные ID."""
        if FOUND_GROUPS_FILE.exists():
            try:
                data = json.loads(FOUND_GROUPS_FILE.read_text(encoding="utf-8"))
                self.found_groups = data.get("groups", {})
            except Exception as e:
                logger.warning("Не удалось загрузить found_groups: %s", e)
        
        if SEEN_GROUPS_FILE.exists():
            try:
                data = json.loads(SEEN_GROUPS_FILE.read_text(encoding="utf-8"))
                self.seen_groups = set(data.get("seen", []))
            except Exception as e:
                logger.warning("Не удалось загрузить seen_groups: %s", e)
    
    def save_state(self):
        """Сохраняет найденные группы и просмотренные ID."""
        try:
            FOUND_GROUPS_FILE.write_text(
                json.dumps({"groups": self.found_groups}, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.warning("Не удалось сохранить found_groups: %s", e)
        
        try:
            SEEN_GROUPS_FILE.write_text(
                json.dumps({"seen": list(self.seen_groups)}, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.warning("Не удалось сохранить seen_groups: %s", e)
    
    async def vk_get(self, method: str, params: dict) -> Optional[dict]:
        """Выполняет запрос к VK API."""
        if not self.session:
            raise RuntimeError("Session not initialized")
        
        params.update({"access_token": VK_TOKEN, "v": VK_API})
        try:
            async with self.session.get(
                f"https://api.vk.com/method/{method}",
                params=params,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as resp:
                data = await resp.json()
                if "error" in data:
                    err = data["error"]
                    logger.warning("VK API error [%s] %s: %s", method, err.get("error_code"), err.get("error_msg"))
                    return None
                return data.get("response")
        except asyncio.TimeoutError:
            logger.warning("Timeout: VK API %s", method)
        except Exception as e:
            logger.error("VK API exception [%s]: %s", method, e)
        return None
    
    def is_group_suitable(self, group: dict) -> bool:
        """Проверяет, подходит ли группа под критерии поиска."""
        name = group.get("name", "").lower()
        description = group.get("description", "").lower()
        members_count = group.get("members_count", 0)
        is_closed = group.get("is_closed", 1)
        type_ = group.get("type", "")
        
        # Фильтр по типу: только группы, не паблики
        if type_ != "group":
            return False
        
        # Фильтр по закрытости: только открытые
        if is_closed != 0:
            return False
        
        # Фильтр по количеству участников
        if not (MIN_MEMBERS <= members_count <= MAX_MEMBERS):
            return False
        
        # Фильтр по стоп-словам
        full_text = f"{name} {description}"
        if any(sw in full_text for sw in STOP_WORDS):
            return False
        
        # Обязательно должно быть слово "перепланировка" или "перепланировки"
        if not re.search(r"\bперепланировк\w*\b", full_text):
            return False
        
        # Обязательно Москва или МО
        if not re.search(r"\b(?:москв|москвы|москве|москву|москвой|москва|московск|московской|московскую|московское|московская|московский)\b", full_text):
            return False
        
        return True
    
    async def search_groups(self, query: str) -> List[dict]:
        """Ищет группы по запросу."""
        logger.info("🔍 Ищу группы по запросу: %s", query)
        groups = []
        offset = 0
        limit = 1000  # максимум за один запрос
        
        while True:
            resp = await self.vk_get("groups.search", {
                "q": query,
                "type": "group",
                "sort": 0,  # по релевантности
                "count": limit,
                "offset": offset,
            })
            if not resp:
                break
            
            items = resp.get("items", [])
            if not items:
                break
            
            for g in items:
                if str(g.get("id", "")) in self.seen_groups:
                    continue
                if self.is_group_suitable(g):
                    groups.append(g)
                    self.seen_groups.add(str(g["id"]))
                    logger.info("✅ Найдена подходящая группа: %s (участников: %d)", g.get("name"), g.get("members_count", 0))
            
            offset += limit
            if offset >= resp.get("count", 0):
                break
            await asyncio.sleep(0.5)
        
        return groups
    
    async def discover_new_groups(self) -> List[dict]:
        """Запускает поиск новых групп по всем ключевым словам."""
        if not VK_TOKEN:
            logger.error("VK_TOKEN не задан в .env")
            return []
        
        new_groups = []
        for query in SEARCH_KEYWORDS:
            try:
                found = await self.search_groups(query)
                new_groups.extend(found)
                await asyncio.sleep(1)
            except Exception as e:
                logger.error("Ошибка поиска по запросу '%s': %s", query, e)
        
        # Сохраняем найденные группы
        for g in new_groups:
            self.found_groups[str(g["id"])] = {
                "name": g.get("name"),
                "screen_name": g.get("screen_name"),
                "members_count": g.get("members_count"),
                "description": g.get("description", "")[:200],
                "added_at": datetime.now().isoformat(),
            }
        
        self.save_state()
        logger.info("🎯 Найдено %d новых групп", len(new_groups))
        return new_groups
    
    async def get_new_group_ids(self) -> List[str]:
        """Возвращает список ID новых групп, которые можно добавить в SCOUT_VK_GROUPS."""
        # Возвращаем только те, которые ещё не в found_groups (на случай перезапуска)
        # и не в seen_groups (уже обработаны)
        # Для простоты — возвращаем все из found_groups
        return list(self.found_groups.keys())
    
    async def start(self):
        """Инициализирует сессию."""
        self.session = aiohttp.ClientSession()
    
    async def stop(self):
        """Закрывает сессию."""
        if self.session:
            await self.session.close()
            self.session = None


async def main():
    """Тестовый запуск discovery."""
    discovery = ScoutDiscovery()
    await discovery.start()
    
    try:
        new_groups = await discovery.discover_new_groups()
        logger.info("✅ Discovery завершён. Новые группы: %s", [g["id"] for g in new_groups])
    finally:
        await discovery.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()],
    )
    asyncio.run(main())