"""
РЎРµСЂРІРёСЃ РґР»СЏ РёРЅС‚РµРіСЂР°С†РёРё СЃ Р’РљРѕРЅС‚Р°РєС‚Рµ API.
РџСѓР±Р»РёРєР°С†РёСЏ РїРѕСЃС‚РѕРІ РІ СЃРѕРѕР±С‰РµСЃС‚РІРѕ + РєРІРёР· TERION.
"""
import os
import logging
from typing import Optional, Dict, List, Tuple
import aiohttp
from datetime import datetime
import json

logger = logging.getLogger(__name__)

# РЎСЃС‹Р»РєР° РЅР° РєРІРёР· TERION - РЅР°СЃС‚СЂРѕР№С‚Рµ РІ .env РёР»Рё РёСЃРїРѕР»СЊР·СѓР№С‚Рµ Р·РЅР°С‡РµРЅРёРµ РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ
QUIZ_LINK = os.getenv("VK_QUIZ_LINK", "https://t.me/Parkhovenko_i_kompaniya_bot?start=quiz")
QUIZ_CTA = f"\n\nрџ‘‰ РЈР·РЅР°Р№С‚Рµ, РјРѕР¶РЅРѕ Р»Рё СѓР·Р°РєРѕРЅРёС‚СЊ РІР°С€Сѓ РїРµСЂРµРїР»Р°РЅРёСЂРѕРІРєСѓ Р·Р° 1 РјРёРЅСѓС‚Сѓ: {QUIZ_LINK}"


class VKService:
    """
    РЎРµСЂРІРёСЃ РґР»СЏ РїСѓР±Р»РёРєР°С†РёРё РєРѕРЅС‚РµРЅС‚Р° РІ Р’РљРѕРЅС‚Р°РєС‚Рµ.
    
    Р¤СѓРЅРєС†РёРѕРЅР°Р»:
    - РџСѓР±Р»РёРєР°С†РёСЏ РїРѕСЃС‚РѕРІ РЅР° СЃС‚РµРЅРµ СЃРѕРѕР±С‰РµСЃС‚РІР° (wall.post)
    - Р—Р°РіСЂСѓР·РєР° С„РѕС‚Рѕ РґР»СЏ РїРѕСЃС‚РѕРІ
    - РљСЂРѕСЃСЃ-РїРѕСЃС‚РёРЅРі РёР· Telegram
    """
    
    def __init__(self):
        self.vk_token = os.getenv("VK_TOKEN", "")
        self.vk_group_id = os.getenv("VK_GROUP_ID", "")
        self.api_version = "5.131"
        self.base_url = "https://api.vk.com/method/"
        
        # РџСЂРѕРІРµСЂСЏРµРј РЅР°Р»РёС‡РёРµ С‚РѕРєРµРЅР°
        if self.vk_token and self.vk_group_id:
            logger.info("вњ… VK Service: РїРѕРґРєР»СЋС‡РµРЅ")
        else:
            logger.warning("вљ пёЏ VK Service: РЅРµ РЅР°СЃС‚СЂРѕРµРЅ (VK_TOKEN РёР»Рё VK_GROUP_ID)")

    async def _make_request(self, method: str, params: dict) -> Optional[dict]:
        """Р’С‹Р·РѕРІ VK API"""
        if not self.vk_token:
            logger.error("VK_TOKEN РЅРµ СѓСЃС‚Р°РЅРѕРІР»РµРЅ")
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
        Р—Р°РіСЂСѓР¶Р°РµС‚ С„РѕС‚Рѕ РЅР° СЃРµСЂРІРµСЂ VK Рё РІРѕР·РІСЂР°С‰Р°РµС‚ photo_id.
        
        Args:
            photo_path: РџСѓС‚СЊ Рє С„Р°Р№Р»Сѓ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ
        
        Returns:
            str: photo_id РёР»Рё None РїСЂРё РѕС€РёР±РєРµ
        """
        if not self.vk_token or not self.vk_group_id:
            return None
        
        try:
            # РџРѕР»СѓС‡Р°РµРј upload_url
            params = {"group_id": self.vk_group_id.replace("-", "")}
            upload_url = await self._make_request("photos.getWallUploadServer", params)
            
            if not upload_url or "upload_url" not in upload_url:
                logger.error("РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ upload_url")
                return None
            
            # Р—Р°РіСЂСѓР¶Р°РµРј С„РѕС‚Рѕ
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field("photo", open(photo_path, "rb"))
                
                async with session.post(upload_url["upload_url"], data=form) as resp:
                    if resp.status != 200:
                        return None
                    upload_result = await resp.json()
            
            # РЎРѕС…СЂР°РЅСЏРµРј С„РѕС‚Рѕ
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
            logger.error(f"РћС€РёР±РєР° Р·Р°РіСЂСѓР·РєРё С„РѕС‚Рѕ РІ VK: {e}")
            return None
    
    async def post(
        self,
        message: str,
        attachments: Optional[List[str]] = None,
        publish_date: Optional[datetime] = None
    ) -> Optional[int]:
        """
        РџСѓР±Р»РёРєСѓРµС‚ РїРѕСЃС‚ РЅР° СЃС‚РµРЅРµ СЃРѕРѕР±С‰РµСЃС‚РІР°.
        
        Args:
            message: РўРµРєСЃС‚ РїРѕСЃС‚Р°
            attachments: РЎРїРёСЃРѕРє attachment (photo123_456)
            publish_date: Р”Р°С‚Р° РѕС‚Р»РѕР¶РµРЅРЅРѕР№ РїСѓР±Р»РёРєР°С†РёРё
        
        Returns:
            int: post_id РёР»Рё None РїСЂРё РѕС€РёР±РєРµ
        """
        if not self.vk_token or not self.vk_group_id:
            logger.error("VK РЅРµ РЅР°СЃС‚СЂРѕРµРЅ")
            return None
        
        params = {
            "owner_id": self.vk_group_id,
            "from_group": 1,
            "message": message[:4000]  # VK Р»РёРјРёС‚
        }
        
        if attachments:
            params["attachments"] = ",".join(attachments)
        
        if publish_date:
            params["publish_date"] = int(publish_date.timestamp())
        
        result = await self._make_request("wall.post", params)
        
        if result and "post_id" in result:
            logger.info(f"вњ… РџРѕСЃС‚ РѕРїСѓР±Р»РёРєРѕРІР°РЅ РІ VK: {result['post_id']}")
            return result["post_id"]
        
        return None
    
    async def post_with_photos(
        self,
        message: str,
        photo_paths: List[str],
        publish_date: Optional[datetime] = None
    ) -> Optional[int]:
        """
        РџСѓР±Р»РёРєСѓРµС‚ РїРѕСЃС‚ СЃ С„РѕС‚РѕРіСЂР°С„РёСЏРјРё.
        
        Args:
            message: РўРµРєСЃС‚ РїРѕСЃС‚Р°
            photo_paths: РЎРїРёСЃРѕРє РїСѓС‚РµР№ Рє С„РѕС‚Рѕ
            publish_date: Р”Р°С‚Р° РїСѓР±Р»РёРєР°С†РёРё
        
        Returns:
            int: post_id РёР»Рё None
        """
        if not photo_paths:
            return await self.post(message, publish_date=publish_date)
        
        attachments = []
        
        # Р—Р°РіСЂСѓР¶Р°РµРј С„РѕС‚Рѕ
        for photo_path in photo_paths:
            photo_id = await self.upload_photo(photo_path)
            if photo_id:
                attachments.append(photo_id)
        
        if not attachments:
            logger.error("РќРµ СѓРґР°Р»РѕСЃСЊ Р·Р°РіСЂСѓР·РёС‚СЊ С„РѕС‚Рѕ РІ VK")
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
        РџСѓР±Р»РёРєСѓРµС‚ РїРѕСЃС‚ СЃРѕ СЃСЃС‹Р»РєРѕР№.
        
        Args:
            message: РўРµРєСЃС‚ РїРѕСЃС‚Р°
            link_url: URL СЃСЃС‹Р»РєРё
            link_title: Р—Р°РіРѕР»РѕРІРѕРє СЃСЃС‹Р»РєРё
            link_photo_url: URL РїСЂРµРІСЊСЋ С„РѕС‚Рѕ
        """
        attachment = link_url
        
        return await self.post(message, attachments=[attachment])
    
    async def get_post_stats(self, post_id: int) -> Optional[Dict]:
        """
        РџРѕР»СѓС‡Р°РµС‚ СЃС‚Р°С‚РёСЃС‚РёРєСѓ РїРѕСЃС‚Р°.
        
        Args:
            post_id: ID РїРѕСЃС‚Р°
        
        Returns:
            dict: РЎС‚Р°С‚РёСЃС‚РёРєР° РёР»Рё None
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


    async def post_with_quiz_cta(
        self,
        message: str,
        attachments: Optional[List[str]] = None,
        publish_date: Optional[datetime] = None
    ) -> Optional[int]:
        """
        РџСѓР±Р»РёРєСѓРµС‚ РїРѕСЃС‚ СЃ РїСЂРёР·С‹РІРѕРј РїСЂРѕР№С‚Рё РєРІРёР· TERION.
        
        Args:
            message: РўРµРєСЃС‚ РїРѕСЃС‚Р°
            attachments: РЎРїРёСЃРѕРє attachment
            publish_date: Р”Р°С‚Р° РїСѓР±Р»РёРєР°С†РёРё
        
        Returns:
            int: post_id РёР»Рё None
        """
        # Р”РѕР±Р°РІР»СЏРµРј CTA РєРІРёР·Р° Рє СЃРѕРѕР±С‰РµРЅРёСЋ
        full_message = f"{message}{QUIZ_CTA}"
        return await self.post(full_message, attachments=attachments, publish_date=publish_date)

    async def send_welcome_message(self, user_id: int) -> bool:
        """
        РћС‚РїСЂР°РІР»СЏРµС‚ РїСЂРёРІРµС‚СЃС‚РІРµРЅРЅРѕРµ СЃРѕРѕР±С‰РµРЅРёРµ РѕС‚ РёРјРµРЅРё РђРЅС‚РѕРЅР°.
        
        Args:
            user_id: ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ Р’Рљ
        
        Returns:
            bool: РЈСЃРїРµС…
        """
        welcome_text = """рџ‘‹ Р—РґСЂР°РІСЃС‚РІСѓР№С‚Рµ! РЇ вЂ” РР-РїРѕРјРѕС‰РЅРёРє РђРЅС‚РѕРЅ РёР· РєРѕРјРїР°РЅРёРё РўР•Р РРћРќ.

РЇ РїРѕРјРѕРіР°СЋ СЃРѕР±СЃС‚РІРµРЅРЅРёРєР°Рј РЅРµРґРІРёР¶РёРјРѕСЃС‚Рё СЂР°Р·РѕР±СЂР°С‚СЊСЃСЏ СЃ РІРѕРїСЂРѕСЃР°РјРё РїРµСЂРµРїР»Р°РЅРёСЂРѕРІРѕРє Рё СЃРѕРіР»Р°СЃРѕРІР°РЅРёР№ РІ РњРѕСЃРєРІРµ.

рџ‘‰ РЈР·РЅР°Р№С‚Рµ Р·Р° 1 РјРёРЅСѓС‚Сѓ, РјРѕР¶РЅРѕ Р»Рё СѓР·Р°РєРѕРЅРёС‚СЊ РІР°С€Сѓ РїРµСЂРµРїР»Р°РЅРёСЂРѕРІРєСѓ вЂ” РїСЂРѕР№РґРёС‚Рµ РЅР°С€ РєРІРёР·: {QUIZ_LINK}

РР»Рё Р·Р°РґР°Р№С‚Рµ РІРѕРїСЂРѕСЃ Р·РґРµСЃСЊ, Рё СЏ РїРѕРјРѕРіСѓ СЂР°Р·РѕР±СЂР°С‚СЊСЃСЏ!

---
*РљРѕРЅСЃСѓР»СЊС‚Р°С†РёСЏ РЅРѕСЃРёС‚ РёРЅС„РѕСЂРјР°С†РёРѕРЅРЅС‹Р№ С…Р°СЂР°РєС‚РµСЂ. Р¤РёРЅР°Р»СЊРЅРѕРµ СЂРµС€РµРЅРёРµ РїРѕРґС‚РІРµСЂР¶РґР°РµС‚ СЌРєСЃРїРµСЂС‚ РўР•Р РРћРќ.*""".format(QUIZ_LINK=QUIZ_LINK)
        
        params = {
            "user_id": user_id,
            "message": welcome_text,
            "random_id": 0  # Р”Р»СЏ СѓРЅРёРєР°Р»СЊРЅРѕСЃС‚Рё СЃРѕРѕР±С‰РµРЅРёСЏ
        }
        
        result = await self._make_request("messages.send", params)
        return result is not None


# Singleton instance
vk_service = VKService()


async def test_vk_connection() -> bool:
    """РџСЂРѕРІРµСЂРєР° РїРѕРґРєР»СЋС‡РµРЅРёСЏ Рє VK"""
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
