import os
import aiohttp
from typing import Optional, List


class VKService:
    """Сервис для интеграции с ВКонтакте API (Асинхронный)"""
    
    def __init__(self):
        self.vk_token = os.getenv("VK_TOKEN")
        self.vk_group_id = os.getenv("VK_GROUP_ID")
        self.api_version = "5.131"
        self.base_url = "https://api.vk.com/method/"
    
    async def send_to_community(self, message: str, attachments: Optional[List[str]] = None) -> bool:
        """Публикация поста на стене сообщества"""
        if not self.vk_token or not self.vk_group_id:
            return False

        params = {
            "owner_id": f"-{self.vk_group_id}",
            "from_group": 1,
            "message": message,
            "access_token": self.vk_token,
            "v": self.api_version
        }

        if attachments:
            params["attachments"] = ",".join(attachments)

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"{self.base_url}wall.post", params=params, timeout=10) as response:
                    result = await response.json()
                    if "response" in result:
                        return True
                    else:
                        print(f"❌ VK Error: {result.get('error')}")
                        return False
            except Exception as e:
                print(f"❌ VK Exception: {e}")
                return False

vk_service = VKService()
