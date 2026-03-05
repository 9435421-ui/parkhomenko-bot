import aiohttp
import logging
import json
from typing import Optional

logger = logging.getLogger(__name__)

class VKPublisher:
    """Публикация в ВКонтакте с кнопками квиз/консультация"""
    
    def __init__(self, token: str, group_id: int):
        self.token = token
        self.group_id = group_id
        self.api_version = "5.199"
    
    async def _make_request(self, method: str, params: dict) -> Optional[dict]:
        params.update({"access_token": self.token, "v": self.api_version})
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.vk.com/method/{method}", params=params) as resp:
                    data = await resp.json()
                    if "error" in data:
                        logger.error(f"VK API error: {data['error']}")
                        return None
                    return data.get("response")
        except Exception as e:
            logger.error(f"VK request error: {e}")
            return None
    
    async def upload_photo(self, image_data: bytes) -> Optional[str]:
        """Загрузка фото на сервер ВК"""
        upload_data = await self._make_request("photos.getWallUploadServer", {"group_id": self.group_id})
        if not upload_data or not upload_data.get("upload_url"):
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field("photo", image_data, filename="photo.jpg", content_type="image/jpeg")
                
                async with session.post(upload_data["upload_url"], data=form) as resp:
                    result = await resp.json()
                    if "error" in result:
                        return None
                    
                    save_data = await self._make_request(
                        "photos.saveWallPhoto",
                        {
                            "group_id": self.group_id,
                            "photo": result.get("photo"),
                            "server": result.get("server"),
                            "hash": result.get("hash")
                        }
                    )
                    
                    if save_data and len(save_data) > 0:
                        photo = save_data[0]
                        return f"photo{photo['owner_id']}_{photo['id']}"
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
            ]
        }
        return json.dumps(buttons, ensure_ascii=False)
    
    async def post_to_wall(self, message: str, photo_id: Optional[str] = None) -> Optional[int]:
        """Публикация поста"""
        attachments = [photo_id] if photo_id else []
        
        params = {
            "owner_id": -self.group_id,
            "from_group": 1,
            "message": message,
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
