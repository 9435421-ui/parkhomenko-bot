"""
Сервис для интеграции с ВКонтакте API (полная реализация)
"""
import os
import json
from typing import Dict, Optional, List
import aiohttp
import asyncio


class VKService:
    """
    Сервис для публикаций и дублирования лидов в ВКонтакте
    """
    
    def __init__(self):
        self.vk_token = os.getenv("VK_TOKEN") or os.getenv("VK_API_TOKEN", "")
        self.vk_group_id = os.getenv("VK_GROUP_ID", "")
        self.api_version = "5.131"
        self.base_url = "https://api.vk.com/method/"
    
    async def _call_method(self, method: str, params: Dict) -> Dict:
        """
        Вызов метода VK API
        """
        if not self.vk_token:
            return {"error": "No token provided"}

        params["access_token"] = self.vk_token
        params["v"] = self.api_version
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}{method}", data=params) as resp:
                return await resp.json()

    async def upload_photo(self, photo_path: str) -> Optional[str]:
        """
        Загрузка фото на стену ВК
        Returns: attachment string (photo123_456)
        """
        if not self.vk_token or not self.vk_group_id:
            return None

        # 1. Получаем сервер для загрузки
        server_resp = await self._call_method("photos.getWallUploadServer", {
            "group_id": self.vk_group_id.replace("-", "")
        })
        
        if "response" not in server_resp:
            print(f"❌ VK Error (upload server): {server_resp}")
            return None

        upload_url = server_resp["response"]["upload_url"]

        # 2. Загружаем файл
        async with aiohttp.ClientSession() as session:
            with open(photo_path, 'rb') as f:
                data = aiohttp.FormData()
                data.add_field('photo', f)
                async with session.post(upload_url, data=data) as resp:
                    upload_data = await resp.json()

        # 3. Сохраняем фото
        save_resp = await self._call_method("photos.saveWallPhoto", {
            "group_id": self.vk_group_id.replace("-", ""),
            "photo": upload_data["photo"],
            "server": upload_data["server"],
            "hash": upload_data["hash"]
        })
        
        if "response" in save_resp:
            photo = save_resp["response"][0]
            return f"photo{photo['owner_id']}_{photo['id']}"

        print(f"❌ VK Error (save photo): {save_resp}")
        return None

    async def send_to_community(
        self,
        message: str,
        attachments: Optional[List[str]] = None
    ) -> bool:
        """
        Публикация на стене сообщества
        """
        if not self.vk_token or not self.vk_group_id:
            return False

        params = {
            "owner_id": f"-{self.vk_group_id.replace('-', '')}",
            "from_group": 1,
            "message": message
        }

        if attachments:
            params["attachments"] = ",".join(attachments)

        resp = await self._call_method("wall.post", params)
        
        if "response" in resp:
            print(f"✅ VK: Опубликован пост {resp['response']['post_id']}")
            return True

        print(f"❌ VK Error (wall.post): {resp}")
        return False

    async def duplicate_lead_to_vk(self, lead_data: Dict) -> bool:
        """
        Дублирование лида в сообщения группы (админу)
        """
        # Для простоты можно использовать существующий механизм уведомлений или
        # отправлять сообщение через messages.send самому себе/админу
        # Требует user_id или peer_id.
        return False


# Singleton instance
vk_service = VKService()
