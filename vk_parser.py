"""
VK Parser вЂ” РјРѕРЅРёС‚РѕСЂРёРЅРі РіСЂСѓРїРї Р’РљРѕРЅС‚Р°РєС‚Рµ.
РџСЂРѕРІРµСЂСЏРµС‚ РЅРѕРІС‹Рµ РїРѕСЃС‚С‹ РїРѕ РєР»СЋС‡РµРІС‹Рј СЃР»РѕРІР°Рј.
"""
import asyncio
import logging
import re
from typing import Optional, List, Dict
import aiohttp
from dotenv import load_dotenv

from config import VK_TOKEN, NOTIFICATIONS_CHANNEL_ID, THREAD_ID_LOGS, SPY_KEYWORDS

load_dotenv()

logger = logging.getLogger(__name__)

# VK API version
VK_API_VERSION = "5.199"


class VKParser:
    """РџР°СЂСЃРµСЂ РіСЂСѓРїРї Р’РљРѕРЅС‚Р°РєС‚Рµ"""
    
    def __init__(self, token: str):
        self.token = token
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _request(self, method: str, params: dict) -> Optional[dict]:
        """Р’С‹Р·РѕРІ VK API"""
        params["access_token"] = self.token
        params["v"] = VK_API_VERSION
        
        url = f"https://api.vk.com/method/{method}"
        
        try:
            async with self.session.get(url, params=params) as resp:
                data = await resp.json()
                if "error" in data:
                    logger.error(f"VK API error: {data['error']}")
                    return None
                return data.get("response")
        except Exception as e:
            logger.error(f"VK request error: {e}")
            return None
    
    async def connect(self):
        """РџРѕРґРєР»СЋС‡РµРЅРёРµ СЃРµСЃСЃРёРё"""
        self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Р—Р°РєСЂС‹С‚РёРµ СЃРµСЃСЃРёРё"""
        if self.session:
            await self.session.close()
    
    async def get_group_id(self, screen_name: str) -> Optional[int]:
        """РџРѕР»СѓС‡РµРЅРёРµ ID РіСЂСѓРїРїС‹ РїРѕ РєРѕСЂРѕС‚РєРѕРјСѓ РёРјРµРЅРё"""
        # РЈР±РёСЂР°РµРј vk.com/ РµСЃР»Рё РµСЃС‚СЊ
        screen_name = screen_name.replace("vk.com/", "")
        
        result = await self._request("groups.getById", {"group_id": screen_name})
        if result and len(result) > 0:
            return result[0]["id"]
        return None
    
    async def get_posts(self, group_id: int, count: int = 10) -> List[Dict]:
        """РџРѕР»СѓС‡РµРЅРёРµ РїРѕСЃР»РµРґРЅРёС… РїРѕСЃС‚РѕРІ РіСЂСѓРїРїС‹"""
        result = await self._request("wall.get", {
            "owner_id": -group_id,
            "count": count,
            "filter": "owner"
        })
        
        if result and "items" in result:
            return result["items"]
        return []
    
    def check_keywords(self, text: str) -> Optional[str]:
        """РџСЂРѕРІРµСЂРєР° С‚РµРєСЃС‚Р° РЅР° РєР»СЋС‡РµРІС‹Рµ СЃР»РѕРІР°"""
        if not text:
            return None
        
        text_lower = text.lower()
        for keyword in SPY_KEYWORDS:
            if keyword.lower() in text_lower:
                return keyword
        return None
    
    async def forward_to_tg(self, post: dict, group_name: str, keyword: str):
        """РџРµСЂРµСЃС‹Р»РєР° РїРѕСЃС‚Р° РІ Telegram"""
        from aiogram import Bot
        
        bot = Bot(token=self.session.get("_bot_token") if self.session else None)
        
        try:
            text = post.get("text", "")
            post_id = post.get("id")
            owner_id = post.get("owner_id")
            
            # Р¤РѕСЂРјРёСЂСѓРµРј СЃСЃС‹Р»РєСѓ
            group_id = abs(owner_id)
            link = f"https://vk.com/wall-{group_id}_{post_id}"
            
            message = f"""рџ“ <b>Р›РёРґ РёР· VK!</b>

рџ’¬ <b>РљР»СЋС‡РµРІРѕРµ СЃР»РѕРІРѕ:</b> {keyword}
рџ“Ќ <b>Р“СЂСѓРїРїР°:</b> {group_name}

рџ“ќ <b>РўРµРєСЃС‚:</b>
{text[:500]}

рџ”— <a href="{link}">РћС‚РєСЂС‹С‚СЊ РІ VK</a>

рџ‘‰ <a href="https://t.me/Parkhovenko_i_kompaniya_bot?start=quiz">РљР’РР—</a> | <a href="tg://user?id=unknown">РќР°РїРёСЃР°С‚СЊ</a>"""
            
            # Р‘РѕС‚ РґР»СЏ РѕС‚РїСЂР°РІРєРё РІ TG
            from config import BOT_TOKEN
            tg_bot = Bot(token=BOT_TOKEN)
            
            await tg_bot.send_message(
                chat_id=NOTIFICATIONS_CHANNEL_ID,
                message_thread_id=THREAD_ID_LOGS,
                text=message,
                parse_mode="HTML"
            )
            
            logger.info(f"вњ… VK Р»РёРґ РїРµСЂРµСЃР»Р°РЅ: {keyword} РёР· {group_name}")
            
            await tg_bot.session.close()
            
        except Exception as e:
            logger.error(f"вќЊ РћС€РёР±РєР° РїРµСЂРµСЃС‹Р»РєРё VK: {e}")


async def check_vk_groups(groups: List[str]):
    """РџСЂРѕРІРµСЂРєР° РіСЂСѓРїРї Р’Рљ РЅР° РЅРѕРІС‹Рµ РїРѕСЃС‚С‹"""
    if not VK_TOKEN:
        logger.error("VK_TOKEN РЅРµ РЅР°Р№РґРµРЅ")
        return
    
    parser = VKParser(VK_TOKEN)
    await parser.connect()
    
    try:
        for group_url in groups:
            logger.info(f"рџ”Ќ РџСЂРѕРІРµСЂСЏСЋ РіСЂСѓРїРїСѓ: {group_url}")
            
            # РџРѕР»СѓС‡Р°РµРј ID РіСЂСѓРїРїС‹
            group_id = await parser.get_group_id(group_url)
            if not group_id:
                logger.error(f"РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕР»СѓС‡РёС‚СЊ ID РіСЂСѓРїРїС‹: {group_url}")
                continue
            
            # РџРѕР»СѓС‡Р°РµРј РїРѕСЃС‚С‹
            posts = await parser.get_posts(group_id, count=5)
            
            for post in posts:
                text = post.get("text", "")
                keyword = parser.check_keywords(text)
                
                if keyword:
                    # РќР°Р№РґРµРЅ РєР»СЋС‡РµРІРёРє!
                    group_name = group_url.replace("vk.com/", "")
                    logger.info(f"рџ”” РќР°Р№РґРµРЅ VK Р»РёРґ: {keyword} РІ {group_name}")
                    
                    # Р—РґРµСЃСЊ РјРѕР¶РЅРѕ РґРѕР±Р°РІРёС‚СЊ Р»РѕРіРёРєСѓ РїРµСЂРµСЃС‹Р»РєРё
                    # await parser.forward_to_tg(post, group_name, keyword)
                    
    finally:
        await parser.close()


async def start_vk_monitoring(groups: List[str], interval: int = 300):
    """
    Р—Р°РїСѓСЃРє РјРѕРЅРёС‚РѕСЂРёРЅРіР° VK РіСЂСѓРїРї.
    
    Args:
        groups: РЎРїРёСЃРѕРє РіСЂСѓРїРї РґР»СЏ РјРѕРЅРёС‚РѕСЂРёРЅРіР° (['himki', 'moscow', ...])
        interval: РРЅС‚РµСЂРІР°Р» РїСЂРѕРІРµСЂРєРё РІ СЃРµРєСѓРЅРґР°С… (РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ 5 РјРёРЅСѓС‚)
    """
    logger.info("рџљЂ Р—Р°РїСѓСЃРє РјРѕРЅРёС‚РѕСЂРёРЅРіР° VK РіСЂСѓРїРї...")
    
    while True:
        try:
            await check_vk_groups(groups)
        except Exception as e:
            logger.error(f"РћС€РёР±РєР° РјРѕРЅРёС‚РѕСЂРёРЅРіР° VK: {e}")
        
        await asyncio.sleep(interval)


if __name__ == "__main__":
    # РџСЂРёРјРµСЂ РёСЃРїРѕР»СЊР·РѕРІР°РЅРёСЏ
    test_groups = ["himki", "moscow"]  # Р—Р°РјРµРЅРёС‚Рµ РЅР° СЃРІРѕРё РіСЂСѓРїРїС‹
    
    logging.basicConfig(level=logging.INFO)
    asyncio.run(start_vk_monitoring(test_groups))
