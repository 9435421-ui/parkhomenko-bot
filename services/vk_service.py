"""
Сервис для интеграции с ВКонтакте API.
Публикация постов в сообщество.
"""
import os
import logging
from typing import Optional, Dict, List
import aiohttp
from datetime import datetime

logger = logging.getLogger(__name__)


class VKService:
    """
    Сервис для публикации контента в ВКонтакте.
    
    Функционал:
    - Публикация постов на стене сообщества (wall.post)
    - Загрузка фото для постов
    - Кросс-постинг из Telegram
    """
    
    def __init__(self):
        self.vk_token = os.getenv("VK_API_TOKEN", "")
        self.vk_group_id = os.getenv("VK_GROUP_ID", "")
        self.api_version = "5.131"
        self.base_url = "https://api.vk.com/method/"
        
        # Проверяем наличие токена
        if self.vk_token and self.vk_group_id:
            logger.info("✅ VK Service: подключен")
        else:
            logger.warning("⚠️ VK Service: не настроен (VK_API_TOKEN или VK_GROUP_ID)")

    async def _make_request(self, method: str, params: dict) -> Optional[dict]:
        """Вызов VK API"""
        if not self.vk_token:
            logger.error("VK_API_TOKEN не установлен")
            return None
        
        url = f"{self.base_url}{method}"
        params["v"] = self.api_version
        params["access_token"] = self.vk_token
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        result = await response.json()
                        if "response" in result:
                            return result["response"]
                        elif "error" in result:
                            logger.error(f"VK Error: {result['error']}")
                            return None
                    else:
                        logger.error(f"VK HTTP Error: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"VK Exception: {e}")
            return None
    
    async def upload_photo(self, photo_path: str) -> Optional[str]:
        """
        Загружает фото на сервер VK и возвращает photo_id.
        
        Args:
            photo_path: Путь к файлу изображения
        
        Returns:
            str: photo_id или None при ошибке
        """
        if not self.vk_token or not self.vk_group_id:
            return None
        
        try:
            # Получаем upload_url
            params = {"group_id": self.vk_group_id.replace("-", "")}
            upload_url = await self._make_request("photos.getWallUploadServer", params)
            
            if not upload_url or "upload_url" not in upload_url:
                logger.error("Не удалось получить upload_url")
                return None
            
            # Загружаем фото
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field("photo", open(photo_path, "rb"))
                
                async with session.post(upload_url["upload_url"], data=form) as resp:
                    if resp.status != 200:
                        return None
                    upload_result = await resp.json()
            
            # Сохраняем фото
            params = {
                "group_id": self.vk_group_id.replace("-", ""),
                "photo": upload_result["photo"],
                "server": upload_result["server"],
                "hash": upload_result["hash"]
            }
            save_result = await self._make_request("photos.saveWallPhoto", params)
            
            if save_result and len(save_result) > 0:
                photo = save_result[0]
                return f"photo{photo['owner_id']}_{photo['id']}"
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка загрузки фото в VK: {e}")
            return None
    
    async def post(
        self,
        message: str,
        attachments: Optional[List[str]] = None,
        publish_date: Optional[datetime] = None
    ) -> Optional[int]:
        """
        Публикует пост на стене сообщества.
        
        Args:
            message: Текст поста
            attachments: Список attachment (photo123_456)
            publish_date: Дата отложенной публикации
        
        Returns:
            int: post_id или None при ошибке
        """
        if not self.vk_token or not self.vk_group_id:
            logger.error("VK не настроен")
            return None
        
        params = {
            "owner_id": self.vk_group_id,
            "from_group": 1,
            "message": message[:4000]  # VK лимит
        }
        
        if attachments:
            params["attachments"] = ",".join(attachments)
        
        if publish_date:
            params["publish_date"] = int(publish_date.timestamp())
        
        result = await self._make_request("wall.post", params)
        
        if result and "post_id" in result:
            logger.info(f"✅ Пост опубликован в VK: {result['post_id']}")
            return result["post_id"]
        
        return None
    
    async def post_with_photos(
        self,
        message: str,
        photo_paths: List[str],
        publish_date: Optional[datetime] = None
    ) -> Optional[int]:
        """
        Публикует пост с фотографиями.
        
        Args:
            message: Текст поста
            photo_paths: Список путей к фото
            publish_date: Дата публикации
        
        Returns:
            int: post_id или None
        """
        if not photo_paths:
            return await self.post(message, publish_date=publish_date)
        
        attachments = []
        
        # Загружаем фото
        for photo_path in photo_paths:
            photo_id = await self.upload_photo(photo_path)
            if photo_id:
                attachments.append(photo_id)
        
        if not attachments:
            logger.error("Не удалось загрузить фото в VK")
            return await self.post(message, publish_date=publish_date)
        
        return await self.post(message, attachments=attachments, publish_date=publish_date)
    
    async def post_link(
        self,
        message: str,
        link_url: str,
        link_title: Optional[str] = None,
        link_photo_url: Optional[str] = None
    ) -> Optional[int]:
        """
        Публикует пост со ссылкой.
        
        Args:
            message: Текст поста
            link_url: URL ссылки
            link_title: Заголовок ссылки
            link_photo_url: URL превью фото
        """
        attachment = link_url
        
        return await self.post(message, attachments=[attachment])
    
    async def get_post_stats(self, post_id: int) -> Optional[Dict]:
        """
        Получает статистику поста.
        
        Args:
            post_id: ID поста
        
        Returns:
            dict: Статистика или None
        """
        if not self.vk_token:
            return None
        
        params = {
            "owner_id": self.vk_group_id,
            "post_ids": post_id
        }
        
        result = await self._make_request("wall.getById", params)
        
        if result and len(result) > 0:
            post = result[0]
            return {
                "views": post.get("views", {}).get("count", 0),
                "likes": post.get("likes", {}).get("count", 0),
                "comments": post.get("comments", {}).get("count", 0),
                "reposts": post.get("reposts", {}).get("count", 0)
            }
        
        return None


# Singleton instance
vk_service = VKService()


async def test_vk_connection() -> bool:
    """Проверка подключения к VK"""
    if not vk_service.vk_token:
        return False
    
    try:
        async with aiohttp.ClientSession() as session:
            params = {
                "access_token": vk_service.vk_token,
                "v": "5.131"
            }
            async with session.get(
                "https://api.vk.com/method/users.get",
                params=params
            ) as response:
                return response.status == 200
    except:
        return False
