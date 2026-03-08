import logging
import aiohttp
import os
from typing import List

logger = logging.getLogger(__name__)

class Discovery:
    """
    Discovery — поиск новых источников (групп VK) для ТЕРИОН.
    """
    def __init__(self, vk_token: str):
        self.vk_token = vk_token
        self.api_version = "5.199"
        self.search_queries = ["ЖК Москва", "Перепланировка", "Ремонт Москва", "Новоселы"]
        self.city_id = 1  # Москва

    async def find_new_sources(self) -> List[str]:
        """
        Ищет новые группы в VK по ключевым словам с ГЕО-фильтром.
        Возвращает список ID групп.
        """
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
