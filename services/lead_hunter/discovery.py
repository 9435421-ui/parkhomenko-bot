import logging
import aiohttp
import os
from typing import List

logger = logging.getLogger(__name__)

class Discovery:
    """
    Discovery — поиск новых источников (групп VK) для ТЕРИОН.
    """
    def __init__(self, vk_token: str = None):
        # Загружаем VK_TOKEN из config, если не передан параметром
        if vk_token is None:
            from config import VK_TOKEN
            vk_token = VK_TOKEN
        
        if not vk_token:
            logger.warning("⚠️ VK_TOKEN не установлен в config. Discovery не сможет работать с VK API.")
        
        self.vk_token = vk_token
        self.api_version = "5.199"
        self.search_queries = ["ЖК Москва", "Перепланировка", "Ремонт Москва", "Новоселы"]
        self.city_id = 1  # Москва

    async def find_new_sources(self) -> List[str]:
        """
        Ищет новые группы в VK по ключевым словам с ГЕО-фильтром.
        Возвращает список ID групп.
        """
        if not self.vk_token:
            logger.error("❌ VK_TOKEN не установлен. Невозможно выполнить поиск в VK.")
            return []
        
        new_group_ids = []
        async with aiohttp.ClientSession() as session:
            for query in self.search_queries:
                try:
                    url = "https://api.vk.com/method/groups.search"
                    params = {
                        "q": query,
                        "city_id": self.city_id,
                        "count": 50,
                        "type": "group",
                        "access_token": self.vk_token,
                        "v": self.api_version
                    }
                    async with session.get(url, params=params) as resp:
                        data = await resp.json()
                        
                        # Проверка ошибок VK API
                        if "error" in data:
                            error_code = data["error"].get("error_code", 0)
                            error_msg = data["error"].get("error_msg", "Unknown error")
                            if error_code == 4:
                                logger.error(f"❌ VK API User authorization failed (код 4): {error_msg}. Проверьте VK_TOKEN в .env")
                                return []
                            else:
                                logger.error(f"❌ VK API ошибка {error_code}: {error_msg}")
                                continue
                        
                        if "response" in data and "items" in data["response"]:
                            for item in data["response"]["items"]:
                                # Проверяем, что это не закрытая группа
                                if item.get("is_closed") == 0:
                                    new_group_ids.append(str(item["id"]))
                    
                    logger.info(f"Discovery: по запросу '{query}' найдено {len(new_group_ids)} открытых групп")
                except Exception as e:
                    logger.error(f"Discovery error for query '{query}': {e}")
        
        # Убираем дубликаты
        return list(set(new_group_ids))

    async def discover_new_resources(self) -> List[str]:
        """
        Алиас для find_new_sources — ищет новые ресурсы в VK.
        Используется в admin.py и других местах системы.
        """
        if not self.vk_token:
            logger.error("❌ VK_TOKEN не установлен. Невозможно выполнить Discovery.")
            return []
        
        return await self.find_new_sources()
