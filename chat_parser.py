"""
Chat Parser вЂ” РјРѕРЅРёС‚РѕСЂРёРЅРі С‡Р°С‚РѕРІ РўРЎР– Рё Р–Рљ С‡РµСЂРµР· Telethon.
РџРµСЂРµСЃС‹Р»Р°РµС‚ СЃРѕРѕР±С‰РµРЅРёСЏ СЃ РєР»СЋС‡РµРІС‹РјРё СЃР»РѕРІР°РјРё РІ С‚РѕРїРёРє 88.
"""
import os
import asyncio
import logging
from telethon import TelegramClient, events
from dotenv import load_dotenv

# РРјРїРѕСЂС‚ РєРѕРЅС„РёРіСѓСЂР°С†РёРё
from config import (
    SPY_KEYWORDS,
    NOTIFICATIONS_CHANNEL_ID,
    THREAD_ID_LOGS,
    BOT_TOKEN
)

from session_manager import get_client

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# РЎРїРёСЃРѕРє С‡Р°С‚РѕРІ РґР»СЏ РјРѕРЅРёС‚РѕСЂРёРЅРіР° (Р±СѓРґСѓС‚ РґРѕР±Р°РІР»РµРЅС‹ РїРѕР»СЊР·РѕРІР°С‚РµР»РµРј)
TARGET_CHATS = [
    # РџСЂРёРјРµСЂ: t.me/c/1849161015/1
    # 1849161015 - ID С‡Р°С‚Р°
    # 1 - С‚РѕРїРёРє (РѕРїС†РёРѕРЅР°Р»СЊРЅРѕ)
]

# РЎРѕРѕР±С‰РµРЅРёРµ РґР»СЏ РїРµСЂРµСЃС‹Р»РєРё
FORWARD_TEMPLATE = """рџ”” <b>Р›РёРґ РёР· С‡Р°С‚Р° РўРЎР–/Р–Рљ!</b>

рџ’¬ <b>РљР»СЋС‡РµРІРѕРµ СЃР»РѕРІРѕ:</b> {keyword}
рџ“Ќ <b>Р§Р°С‚:</b> {chat_title}

рџ“ќ <b>РЎРѕРѕР±С‰РµРЅРёРµ:</b>
{message_text}

рџ”— <a href="{message_link}">РћС‚РєСЂС‹С‚СЊ РІ С‡Р°С‚Рµ</a>

рџ‘‰ <a href="https://t.me/Parkhovenko_i_kompaniya_bot?start=quiz">РљР’РР—</a> | <a href="tg://user?id=unknown">РќР°РїРёСЃР°С‚СЊ</a>"""


def check_keywords(text: str) -> str | None:
    """
    РџСЂРѕРІРµСЂСЏРµС‚ СЃРѕРѕР±С‰РµРЅРёРµ РЅР° РЅР°Р»РёС‡РёРµ РєР»СЋС‡РµРІС‹С… СЃР»РѕРІ.
    Returns: РЅР°Р№РґРµРЅРЅРѕРµ РєР»СЋС‡РµРІРѕРµ СЃР»РѕРІРѕ РёР»Рё None
    """
    if not text:
        return None
    
    text_lower = text.lower()
    for keyword in SPY_KEYWORDS:
        if keyword.lower() in text_lower:
            return keyword
    return None


async def forward_to_tg(message_text: str, chat_title: str, message_link: str, keyword: str):
    """
    РџРµСЂРµСЃС‹Р»Р°РµС‚ СЃРѕРѕР±С‰РµРЅРёРµ РІ С‚РѕРїРёРє 88 С‡РµСЂРµР· aiogram Р±РѕС‚Р°.
    """
    from aiogram import Bot
    
    bot = Bot(token=BOT_TOKEN)
    
    try:
        text = FORWARD_TEMPLATE.format(
            keyword=keyword,
            chat_title=chat_title,
            message_text=message_text[:500],
            message_link=message_link
        )
        
        await bot.send_message(
            chat_id=NOTIFICATIONS_CHANNEL_ID,
            message_thread_id=THREAD_ID_LOGS,
            text=text,
            parse_mode="HTML"
        )
        logger.info(f"вњ… Р›РёРґ РїРµСЂРµСЃР»Р°РЅ: {keyword} РёР· {chat_title}")
        
    except Exception as e:
        logger.error(f"вќЊ РћС€РёР±РєР° РїРµСЂРµСЃС‹Р»РєРё: {e}")
        
    finally:
        await bot.session.close()


async def process_message(event):
    """
    РћР±СЂР°Р±Р°С‚С‹РІР°РµС‚ РІС…РѕРґСЏС‰РµРµ СЃРѕРѕР±С‰РµРЅРёРµ РёР· С‡Р°С‚Р°.
    """
    try:
        # РџРѕР»СѓС‡Р°РµРј С‚РµРєСЃС‚ СЃРѕРѕР±С‰РµРЅРёСЏ
        if event.message.text:
            message_text = event.message.text
        elif event.message.message:
            message_text = event.message.message
        else:
            return
        
        # РџСЂРѕРІРµСЂСЏРµРј РЅР° РєР»СЋС‡РµРІС‹Рµ СЃР»РѕРІР°
        keyword = check_keywords(message_text)
        if not keyword:
            return
        
        # РџРѕР»СѓС‡Р°РµРј РёРЅС„РѕСЂРјР°С†РёСЋ Рѕ С‡Р°С‚Рµ
        chat = await event.get_chat()
        chat_title = getattr(chat, 'title', 'РќРµРёР·РІРµСЃС‚РЅС‹Р№ С‡Р°С‚')
        
        # Р¤РѕСЂРјРёСЂСѓРµРј СЃСЃС‹Р»РєСѓ РЅР° СЃРѕРѕР±С‰РµРЅРёРµ
        chat_id = event.chat_id
        message_id = event.message.id
        
        # РЎСЃС‹Р»РєР° С„РѕСЂРјР°С‚Р° t.me/c/ID/ID
        if str(chat_id).startswith("-100"):
            clean_id = str(chat_id).replace("-100", "")
            message_link = f"https://t.me/c/{clean_id}/{message_id}"
        else:
            message_link = f"https://t.me/{chat.username}/{message_id}" if hasattr(chat, 'username') and chat.username else f"https://t.me/c/{chat_id}/{message_id}"
        
        logger.info(f"рџ”” РќР°Р№РґРµРЅ Р»РёРґ! РљР»СЋС‡РµРІРѕРµ СЃР»РѕРІРѕ: {keyword} РІ С‡Р°С‚Рµ: {chat_title}")
        
        # РџРµСЂРµСЃС‹Р»Р°РµРј РІ С‚РѕРїРёРє 88
        await forward_to_tg(message_text, chat_title, message_link, keyword)
        
    except Exception as e:
        logger.error(f"вќЊ РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё СЃРѕРѕР±С‰РµРЅРёСЏ: {e}")


async def start_monitoring():
    """
    Р—Р°РїСѓСЃРєР°РµС‚ РјРѕРЅРёС‚РѕСЂРёРЅРі С‡Р°С‚РѕРІ.
    """
    logger.info("рџљЂ Р—Р°РїСѓСЃРє РјРѕРЅРёС‚РѕСЂРёРЅРіР° С‡Р°С‚РѕРІ РўРЎР–/Р–Рљ...")
    
    # РџРѕР»СѓС‡Р°РµРј РєР»РёРµРЅС‚ Telethon
    client = await get_client()
    
    if not client:
        logger.error("вќЊ РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє Telegram")
        return
    
    logger.info("вњ… РџРѕРґРєР»СЋС‡РµРЅРѕ Рє Telegram")
    
    if not TARGET_CHATS:
        logger.warning("вљ пёЏ РЎРїРёСЃРѕРє С†РµР»РµРІС‹С… С‡Р°С‚РѕРІ РїСѓСЃС‚!")
        logger.info("   Р”РѕР±Р°РІСЊС‚Рµ С‡Р°С‚С‹ РІ РїРµСЂРµРјРµРЅРЅСѓСЋ TARGET_CHATS")
        logger.info("   РџСЂРёРјРµСЂ: TARGET_CHATS = ['https://t.me/c/1849161015/1']")
    
    # Р”РѕР±Р°РІР»СЏРµРј РѕР±СЂР°Р±РѕС‚С‡РёРєРё РґР»СЏ РєР°Р¶РґРѕРіРѕ С‡Р°С‚Р°
    for chat_url in TARGET_CHATS:
        try:
            # РР·РІР»РµРєР°РµРј ID С‡Р°С‚Р° РёР· СЃСЃС‹Р»РєРё
            # t.me/c/1849161015/1 -> 1849161015
            chat_id = chat_url.replace("https://t.me/c/", "").replace("https://t.me/", "").split("/")[0]
            chat_id = int(chat_id)
            
            # РџРѕРґРїРёСЃС‹РІР°РµРјСЃСЏ РЅР° РЅРѕРІС‹Рµ СЃРѕРѕР±С‰РµРЅРёСЏ
            @client.on(events.NewMessage(chats=chat_id))
            async def handler(event):
                await process_message(event)
            
            logger.info(f"вњ… РџРѕРґРїРёСЃР°РЅ РЅР° С‡Р°С‚: {chat_url}")
            
        except Exception as e:
            logger.error(f"вќЊ РћС€РёР±РєР° РїРѕРґРїРёСЃРєРё РЅР° {chat_url}: {e}")
    
    logger.info("рџЋ‰ РњРѕРЅРёС‚РѕСЂРёРЅРі Р·Р°РїСѓС‰РµРЅ!")
    logger.info("   РћР¶РёРґР°РЅРёРµ СЃРѕРѕР±С‰РµРЅРёР№...")
    
    # Р—Р°РїСѓСЃРєР°РµРј РєР»РёРµРЅС‚ (Р±Р»РѕРєРёСЂСѓСЋС‰РёР№ РІС‹Р·РѕРІ)
    await client.run_until_disconnected()


if __name__ == "__main__":
    # Р—Р°РїСѓСЃРє
    asyncio.run(start_monitoring())
