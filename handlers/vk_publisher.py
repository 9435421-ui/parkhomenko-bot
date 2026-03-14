<<<<<<< HEAD
import aiohttp
import logging
import json
from typing import Optional

logger = logging.getLogger(__name__)

class VKPublisher:
    """Публикация в ВКонтакте с кнопками квиз/консультация"""
=======
"""
VK Publisher Module — публикация в ВКонтакте
"""
import aiohttp
import logging
from typing import Optional, List, Dict
import asyncio

logger = logging.getLogger(__name__)


class VKPublisher:
    """Клиент для публикации в ВКонтакте"""
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
    
    def __init__(self, token: str, group_id: int):
        self.token = token
        self.group_id = group_id
        self.api_version = "5.199"
<<<<<<< HEAD
    
    async def _make_request(self, method: str, params: dict) -> Optional[dict]:
        params.update({"access_token": self.token, "v": self.api_version})
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.vk.com/method/{method}", params=params) as resp:
                    data = await resp.json()
=======
        self.base_url = "https://api.vk.com/method"
    
    async def _make_request(self, method: str, params: dict) -> Optional[dict]:
        """Выполнить запрос к API VK"""
        params.update({
            "access_token": self.token,
            "v": self.api_version
        })
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/{method}", params=params) as response:
                    data = await response.json()
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
                    if "error" in data:
                        logger.error(f"VK API error: {data['error']}")
                        return None
                    return data.get("response")
        except Exception as e:
            logger.error(f"VK request error: {e}")
            return None
    
    async def upload_photo(self, image_data: bytes) -> Optional[str]:
        """Загрузка фото на сервер ВК"""
<<<<<<< HEAD
        upload_data = await self._make_request("photos.getWallUploadServer", {"group_id": self.group_id})
        if not upload_data or not upload_data.get("upload_url"):
=======
        upload_url_data = await self._make_request(
            "photos.getWallUploadServer",
            {"group_id": self.group_id}
        )
        
        if not upload_url_data:
            return None
        
        upload_url = upload_url_data.get("upload_url")
        if not upload_url:
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field("photo", image_data, filename="photo.jpg", content_type="image/jpeg")
                
<<<<<<< HEAD
                async with session.post(upload_data["upload_url"], data=form) as resp:
                    result = await resp.json()
                    if "error" in result:
=======
                async with session.post(upload_url, data=form) as response:
                    upload_result = await response.json()
                    
                    if "error" in upload_result:
                        logger.error(f"VK upload error: {upload_result}")
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
                        return None
                    
                    save_data = await self._make_request(
                        "photos.saveWallPhoto",
                        {
                            "group_id": self.group_id,
<<<<<<< HEAD
                            "photo": result.get("photo"),
                            "server": result.get("server"),
                            "hash": result.get("hash")
=======
                            "photo": upload_result.get("photo"),
                            "server": upload_result.get("server"),
                            "hash": upload_result.get("hash")
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
                        }
                    )
                    
                    if save_data and len(save_data) > 0:
                        photo = save_data[0]
                        return f"photo{photo['owner_id']}_{photo['id']}"
<<<<<<< HEAD
        except Exception as e:
            logger.error(f"VK upload error: {e}")
        return None
    
    def create_buttons(self, quiz_link: str = None, consult_link: str = None) -> str:
        """Кнопки: Квиз и Консультация"""
        if not quiz_link:
            quiz_link = "https://vk.com/app51781232" # Дефолтная ссылка на квиз ВК
        if not consult_link:
            consult_link = "https://t.me/terion_bot?start=consult"
        
        buttons = {
            "inline": True,
            "buttons": [
                [{"action": {"type": "open_link", "link": quiz_link, "label": "📝 Пройти квиз"}}],
                [{"action": {"type": "open_link", "link": consult_link, "label": "💬 Бесплатная консультация"}}]
=======
                    
        except Exception as e:
            logger.error(f"VK photo upload error: {e}")
        
        return None
    
    async def create_buttons(self) -> str:
        """Создание кнопок для поста ВК (JSON)"""
        import json
        buttons = {
            "inline": True,
            "buttons": [
                [
                    {
                        "action": {
                            "type": "open_link",
                            "link": "https://t.me/terion_bot?start=quiz",
                            "label": "📝 Пройти квиз"
                        }
                    }
                ],
                [
                    {
                        "action": {
                            "type": "open_link",
                            "link": "https://t.me/terion_bot?start=consult",
                            "label": "💬 Бесплатная консультация"
                        }
                    }
                ]
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
            ]
        }
        return json.dumps(buttons, ensure_ascii=False)
    
<<<<<<< HEAD
    async def post_to_wall(self, message: str, photo_id: Optional[str] = None) -> Optional[int]:
        """Публикация поста"""
        attachments = [photo_id] if photo_id else []
=======
    async def post_to_wall(
        self,
        message: str,
        photo_id: Optional[str] = None,
        add_buttons: bool = True
    ) -> Optional[int]:
        """Публикация поста на стену группы"""
        attachments = []
        if photo_id:
            attachments.append(photo_id)
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
        
        params = {
            "owner_id": -self.group_id,
            "from_group": 1,
            "message": message,
<<<<<<< HEAD
            "attachments": ",".join(attachments),
            "keyboard": self.create_buttons()
        }
        
        result = await self._make_request("wall.post", params)
        return result.get("post_id") if result else None
    
    async def post_text_only(self, message: str) -> Optional[int]:
        return await self.post_to_wall(message, None)
    
    async def post_with_photo(self, message: str, image_bytes: bytes) -> Optional[int]:
        photo_id = await self.upload_photo(image_bytes)
        if not photo_id:
            return await self.post_text_only(message)
        return await self.post_to_wall(message, photo_id)
=======
            "attachments": ",".join(attachments) if attachments else ""
        }
        
        if add_buttons:
            params["keyboard"] = await self.create_buttons()
        
        result = await self._make_request("wall.post", params)
        if result:
            post_id = result.get("post_id")
            logger.info(f"VK post created: {post_id}")
            return post_id
        
        return None
    
    async def post_text_only(self, message: str, add_buttons: bool = True) -> Optional[int]:
        """Публикация только текста"""
        return await self.post_to_wall(message, None, add_buttons)
    
    async def post_with_photo(
        self,
        message: str,
        image_bytes: bytes,
        add_buttons: bool = True
    ) -> Optional[int]:
        """Публикация с фото"""
        photo_id = await self.upload_photo(image_bytes)
        if not photo_id:
            return await self.post_text_only(message, add_buttons)
        
        return await self.post_to_wall(message, photo_id, add_buttons)
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
