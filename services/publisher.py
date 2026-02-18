import os
import logging
from typing import Dict, Optional
import aiohttp
from aiogram import Bot

logger = logging.getLogger(__name__)

class Publisher:
    """Публикация контента в Telegram и VK"""
    
    def __init__(self, bot: Bot = None):
        self.bot = bot
        self.tg_channels = {
            'terion': int(os.getenv('CHANNEL_ID_TERION', 0)),
            'dom_grad': int(os.getenv('CHANNEL_ID_DOM_GRAD', 0))
        }
        self.vk_token = os.getenv('VK_TOKEN')
        self.vk_group = os.getenv('VK_GROUP_ID')
        
    async def publish_to_telegram(self, channel_id: int, text: str, image: bytes = None) -> bool:
        """Публикация в Telegram канал"""
        if not self.bot:
            logger.error("❌ Publisher: Bot instance not provided")
            return False
            
        try:
            if image:
                from aiogram.types import BufferedInputFile
                photo = BufferedInputFile(image, filename="post_image.jpg")
                await self.bot.send_photo(channel_id, photo=photo, caption=text[:1024])
            else:
                await self.bot.send_message(channel_id, text)
            logger.info(f"✅ Опубликовано в TG канал {channel_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка публикации в TG: {e}")
            return False
    
    # Подпись эксперта для VK
    VK_SIGNATURE = "\n\n---\n🏡 Эксперт: Юлия Пархоменко\n#TERION #ИИ_Ассистент"
    
    async def publish_to_vk(self, text: str, image: bytes = None, add_signature: bool = True) -> bool:
        """Публикация в VK группу через API"""
        if not self.vk_token or not self.vk_group:
            logger.warning("⚠️ VK_TOKEN или VK_GROUP_ID не настроены")
            return False
            
        try:
            # Добавляем подпись эксперта
            if add_signature:
                text = text + self.VK_SIGNATURE
            
            # Базовая публикация текста
            url = "https://api.vk.com/method/wall.post"
            params = {
                'access_token': self.vk_token,
                'owner_id': f"-{self.vk_group}",
                'message': text,
                'v': '5.199'
            }
            
            # Если есть изображение, нужно сначала загрузить его в ВК
            attachments = ""
            if image:
                photo_attachment = await self._upload_photo_to_vk(image)
                if photo_attachment:
                    attachments = photo_attachment
                    params['attachments'] = attachments

            async with aiohttp.ClientSession() as session:
                async with session.post(url, params=params) as resp:
                    result = await resp.json()
                    if 'error' in result:
                        logger.error(f"VK API error: {result['error']}")
                        return False
                    logger.info(f"✅ Опубликовано в VK")
                    return True
                    
        except Exception as e:
            logger.error(f"❌ Ошибка публикации в VK: {e}")
            return False

    async def _upload_photo_to_vk(self, image_bytes: bytes) -> Optional[str]:
        """Загрузка фото на сервера ВК для прикрепления к посту"""
        try:
            # 1. Получаем адрес для загрузки
            get_url = "https://api.vk.com/method/photos.getWallUploadServer"
            params = {
                'access_token': self.vk_token,
                'group_id': self.vk_group,
                'v': '5.199'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(get_url, params=params) as resp:
                    data = await resp.json()
                    upload_url = data.get('response', {}).get('upload_url')
                    
                if not upload_url:
                    return None
                
                # 2. Загружаем файл
                data = aiohttp.FormData()
                data.add_field('photo', image_bytes, filename='photo.jpg', content_type='image/jpeg')
                
                async with session.post(upload_url, data=data) as resp:
                    upload_data = await resp.json()
                
                # 3. Сохраняем фото
                save_url = "https://api.vk.com/method/photos.saveWallPhoto"
                save_params = {
                    'access_token': self.vk_token,
                    'group_id': self.vk_group,
                    'photo': upload_data.get('photo'),
                    'server': upload_data.get('server'),
                    'hash': upload_data.get('hash'),
                    'v': '5.199'
                }
                
                async with session.get(save_url, params=save_params) as resp:
                    saved_data = await resp.json()
                    photo = saved_data.get('response', [{}])[0]
                    if photo:
                        return f"photo{photo['owner_id']}_{photo['id']}"
            
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки фото в VK: {e}")
            return None
    
    async def publish_to_max(self, text: str, title: str = "") -> bool:
        """Публикация в Max.ru"""
        device_token = os.getenv("MAX_DEVICE_TOKEN", "").strip()
        subsite_id = os.getenv("MAX_SUBSITE_ID", "").strip()

        if not device_token or not subsite_id:
            logger.warning("⚠️ MAX_DEVICE_TOKEN или MAX_SUBSITE_ID не настроены")
            return False

        url = f"https://api.max.ru/v1.9/subsite/{subsite_id}/content"
        headers = {
            "X-Device-Token": device_token,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {device_token}",
        }

        import re
        body_plain = re.sub(r"<[^>]+>", "", text)
        body_plain = re.sub(r"&nbsp;", " ", body_plain).strip()

        payload = {
            "title": (title or "Новости TERION")[:200],
            "body": body_plain[:5000],
            "type": "post",
        }

        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    url, headers=headers, json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status == 200:
                        logger.info("✅ Опубликовано в Max.ru")
                        return True
                    else:
                        error_text = await resp.text()
                        logger.error(f"❌ Max.ru error {resp.status}: {error_text[:200]}")
                        return False
        except Exception as e:
            logger.error(f"❌ Ошибка публикации в Max.ru: {e}")
            return False

    async def publish_all(self, text: str, image: bytes = None, title: str = "") -> Dict[str, bool]:
        """Публикация во все настроенные каналы: Telegram, VK, Max.ru"""
        results = {}

        # Telegram
        for name, channel_id in self.tg_channels.items():
            if channel_id:
                results[f'tg_{name}'] = await self.publish_to_telegram(channel_id, text, image)

        # VK
        if self.vk_token and self.vk_group:
            results['vk'] = await self.publish_to_vk(text, image)

        # Max.ru
        if os.getenv("MAX_DEVICE_TOKEN"):
            results['max'] = await self.publish_to_max(text, title)

        return results

# Singleton
publisher = Publisher()
