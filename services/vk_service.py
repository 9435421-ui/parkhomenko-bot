import os
import aiohttp
import json
from typing import Optional, List, Dict


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

    async def upload_photos(self, image_data_list: List[bytes]) -> List[str]:
        """
        Загрузка нескольких фото на сервер ВК

        Returns:
            List[str]: Список идентификаторов вложений (photoXXXX_XXXX)
        """
        if not self.vk_token or not self.vk_group_id:
            return []

        attachment_ids = []
        async with aiohttp.ClientSession() as session:
            try:
                # 1. Получение сервера загрузки
                params = {
                    "group_id": self.vk_group_id,
                    "access_token": self.vk_token,
                    "v": self.api_version
                }
                async with session.get(f"{self.base_url}photos.getWallUploadServer", params=params) as resp:
                    server_data = await resp.json()
                    upload_url = server_data.get("response", {}).get("upload_url")

                if not upload_url:
                    return []

                for image_data in image_data_list:
                    # 2. Загрузка файла
                    data = aiohttp.FormData()
                    data.add_field('photo', image_data, filename='photo.jpg', content_type='image/jpeg')

                    async with session.post(upload_url, data=data) as upload_resp:
                        upload_result = await upload_resp.json()

                    # 3. Сохранение фото
                    save_params = {
                        "group_id": self.vk_group_id,
                        "photo": upload_result.get("photo"),
                        "server": upload_result.get("server"),
                        "hash": upload_result.get("hash"),
                        "access_token": self.vk_token,
                        "v": self.api_version
                    }
                    async with session.post(f"{self.base_url}photos.saveWallPhoto", params=save_params) as save_resp:
                        saved_photo_data = await save_resp.json()

                    photo_info = saved_photo_data.get("response", [{}])[0]
                    if photo_info:
                        attachment_ids.append(f"photo{photo_info['owner_id']}_{photo_info['id']}")

            except Exception as e:
                print(f"❌ VK Upload Exception: {e}")

        return attachment_ids


vk_service = VKService()
