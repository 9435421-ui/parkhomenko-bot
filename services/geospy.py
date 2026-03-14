"""
Geo Spy Module вЂ” РјРѕРЅРёС‚РѕСЂРёРЅРі РіРµРѕ-С‡Р°С‚РѕРІ РґР»СЏ РїРѕРёСЃРєР° Р»РёРґРѕРІ.
Р’РєР»СЋС‡РµРЅ: GEO_SPY_ENABLED = True
"""
import asyncio
import logging
from typing import Optional
from aiogram import Bot

from config import (
    GEO_SPY_ENABLED,
    GEO_CHAT_ID,
    GEO_CHAT_1_ID,
    NOTIFICATIONS_CHANNEL_ID,
    THREAD_ID_LOGS,
    SPY_KEYWORDS,
    BOT_TOKEN
)

logger = logging.getLogger(__name__)

# РњРѕРЅРёС‚РѕСЂРёРјС‹Рµ С‡Р°С‚С‹
MONITORED_CHATS = [
    GEO_CHAT_ID,
    GEO_CHAT_1_ID,
]

# РР·РІРµСЃС‚РЅС‹Рµ С‡Р°С‚С‹ Р·Р°СЃС‚СЂРѕР№С‰РёРєРѕРІ
DEVELOPER_CHATS = {
    "@perekrestok_moscow": GEO_CHAT_ID,
    "@samolet_msk": GEO_CHAT_1_ID,
    "@pik_group": None,  # Р”РѕР±Р°РІРёС‚СЊ ID
    "@lod_group": None,  # Р”РѕР±Р°РІРёС‚СЊ ID
    "@etalon_group": None,  # Р”РѕР±Р°РІРёС‚СЊ ID
}


async def check_message_for_keywords(text: str) -> Optional[str]:
    """
    РџСЂРѕРІРµСЂСЏРµС‚ СЃРѕРѕР±С‰РµРЅРёРµ РЅР° РЅР°Р»РёС‡РёРµ РєР»СЋС‡РµРІС‹С… СЃР»РѕРІ.
    
    Returns:
        str: РќР°Р№РґРµРЅРЅРѕРµ РєР»СЋС‡РµРІРѕРµ СЃР»РѕРІРѕ РёР»Рё None
    """
    if not text:
        return None
    
    text_lower = text.lower()
    
    for keyword in SPY_KEYWORDS:
        if keyword.lower() in text_lower:
            return keyword
    
    return None


async def send_hot_lead_alert(
    bot: Bot,
    chat_id: int,
    message_text: str,
    user_name: str = "РќРµРёР·РІРµСЃС‚РЅС‹Р№",
    message_id: int = 0
) -> bool:
    """
    РћС‚РїСЂР°РІР»СЏРµС‚ СѓРІРµРґРѕРјР»РµРЅРёРµ Рѕ РіРѕСЂСЏС‡РµРј Р»РёРґРµ РІ С‚РѕРїРёРє THREAD_ID_LOGS (88).
    """
    keyword = await check_message_for_keywords(message_text)
    if not keyword:
        return False
    
    try:
        alert_text = f"""рџ”Ґ <b>Р“РћР РЇР§РР™ Р›РР”!</b>

рџ’¬ <b>РљР»СЋС‡РµРІРѕРµ СЃР»РѕРІРѕ:</b> {keyword}
рџ‘¤ <b>РћС‚:</b> {user_name}
рџ“Ќ <b>Р§Р°С‚:</b> {chat_id}

рџ“ќ <b>РЎРѕРѕР±С‰РµРЅРёРµ:</b>
{message_text[:500]}

рџ”— <a href="https://t.me/c/{str(chat_id).replace('-100', '')}/{message_id}">РћС‚РєСЂС‹С‚СЊ РІ С‡Р°С‚Рµ</a>

рџ‘‰ <a href="https://t.me/Parkhovenko_i_kompaniya_bot?start=quiz">РљР’РР—</a> | <a href="tg://user?id=unknown">РќР°РїРёСЃР°С‚СЊ</a>"""
        
        await bot.send_message(
            chat_id=NOTIFICATIONS_CHANNEL_ID,
            message_thread_id=THREAD_ID_LOGS,
            text=alert_text,
            parse_mode="HTML"
        )
        
        logger.info(f"рџ”Ґ Hot lead found: {keyword} from chat {chat_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send hot lead alert: {e}")
        return False


async def start_spy_monitoring(bot: Bot):
    """
    Р—Р°РїСѓСЃРєР°РµС‚ РјРѕРЅРёС‚РѕСЂРёРЅРі РіРµРѕ-С‡Р°С‚РѕРІ.
    """
    if not GEO_SPY_ENABLED:
        logger.info("Geo Spy: РѕС‚РєР»СЋС‡РµРЅ (GEO_SPY_ENABLED = False)")
        return
    
    logger.info("рџ”Ґ Geo Spy: РјРѕРЅРёС‚РѕСЂРёРЅРі Р·Р°РїСѓС‰РµРЅ")
    
    # Р—РґРµСЃСЊ Р±СѓРґРµС‚ Р»РѕРіРёРєР° РјРѕРЅРёС‚РѕСЂРёРЅРіР° С‡РµСЂРµР· Telegram API
    # Р”Р»СЏ inline-Р±РѕС‚РѕРІ СЌС‚Рѕ РјРѕР¶РµС‚ Р±С‹С‚СЊ С‡РµСЂРµР· webhooks РёР»Рё long polling
    
    # РџСЂРёРјРµСЂ СЃС‚СЂСѓРєС‚СѓСЂС‹ РґР»СЏ РѕР±СЂР°Р±РѕС‚РєРё РІС…РѕРґСЏС‰РёС… СЃРѕРѕР±С‰РµРЅРёР№:
    """
    async def process_incoming_message(chat_id: int, text: str, user_name: str, message_id: int):
        if chat_id in MONITORED_CHATS:
            await send_hot_lead_alert(bot, chat_id, text, user_name, message_id)
    """


# Р¤СѓРЅРєС†РёСЏ РґР»СЏ РёРЅС‚РµРіСЂР°С†РёРё СЃ РѕР±СЂР°Р±РѕС‚С‡РёРєР°РјРё СЃРѕРѕР±С‰РµРЅРёР№
async def check_and_notify(
    bot: Bot,
    chat_id: int,
    text: str,
    user_name: str = "РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ",
    message_id: int = 0
) -> bool:
    """
    РџСЂРѕРІРµСЂСЏРµС‚ СЃРѕРѕР±С‰РµРЅРёРµ Рё РѕС‚РїСЂР°РІР»СЏРµС‚ СѓРІРµРґРѕРјР»РµРЅРёРµ РїСЂРё СЃРѕРІРїР°РґРµРЅРёРё.
    
    Returns:
        bool: True РµСЃР»Рё РѕС‚РїСЂР°РІР»РµРЅРѕ СѓРІРµРґРѕРјР»РµРЅРёРµ
    """
    if chat_id not in MONITORED_CHATS:
        return False
    
    return await send_hot_lead_alert(bot, chat_id, text, user_name, message_id)


# Singleton
geo_spy = {
    "enabled": GEO_SPY_ENABLED,
    "chats": MONITORED_CHATS,
    "keywords": SPY_KEYWORDS,
}
