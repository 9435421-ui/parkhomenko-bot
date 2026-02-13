"""
Geo Spy Module — мониторинг гео-чатов для поиска лидов.
Включен: GEO_SPY_ENABLED = True
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

# Мониторимые чаты
MONITORED_CHATS = [
    GEO_CHAT_ID,
    GEO_CHAT_1_ID,
]

# Известные чаты застройщиков
DEVELOPER_CHATS = {
    "@perekrestok_moscow": GEO_CHAT_ID,
    "@samolet_msk": GEO_CHAT_1_ID,
    "@pik_group": None,  # Добавить ID
    "@lod_group": None,  # Добавить ID
    "@etalon_group": None,  # Добавить ID
}


async def check_message_for_keywords(text: str) -> Optional[str]:
    """
    Проверяет сообщение на наличие ключевых слов.
    
    Returns:
        str: Найденное ключевое слово или None
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
    user_name: str = "Неизвестный",
    message_id: int = 0
) -> bool:
    """
    Отправляет уведомление о горячем лиде в топик THREAD_ID_LOGS (88).
    """
    keyword = await check_message_for_keywords(message_text)
    if not keyword:
        return False
    
    try:
        alert_text = f"""🔥 <b>ГОРЯЧИЙ ЛИД!</b>

💬 <b>Ключевое слово:</b> {keyword}
👤 <b>От:</b> {user_name}
📍 <b>Чат:</b> {chat_id}

📝 <b>Сообщение:</b>
{message_text[:500]}

🔗 <a href="https://t.me/c/{str(chat_id).replace('-100', '')}/{message_id}">Открыть в чате</a>

👉 <a href="https://t.me/TERION_KvizBot?start=quiz">КВИЗ</a> | <a href="tg://user?id=unknown">Написать</a>"""
        
        await bot.send_message(
            chat_id=NOTIFICATIONS_CHANNEL_ID,
            message_thread_id=THREAD_ID_LOGS,
            text=alert_text,
            parse_mode="HTML"
        )
        
        logger.info(f"🔥 Hot lead found: {keyword} from chat {chat_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send hot lead alert: {e}")
        return False


async def start_spy_monitoring(bot: Bot):
    """
    Запускает мониторинг гео-чатов.
    """
    if not GEO_SPY_ENABLED:
        logger.info("Geo Spy: отключен (GEO_SPY_ENABLED = False)")
        return
    
    logger.info("🔥 Geo Spy: мониторинг запущен")
    
    # Здесь будет логика мониторинга через Telegram API
    # Для inline-ботов это может быть через webhooks или long polling
    
    # Пример структуры для обработки входящих сообщений:
    """
    async def process_incoming_message(chat_id: int, text: str, user_name: str, message_id: int):
        if chat_id in MONITORED_CHATS:
            await send_hot_lead_alert(bot, chat_id, text, user_name, message_id)
    """


# Функция для интеграции с обработчиками сообщений
async def check_and_notify(
    bot: Bot,
    chat_id: int,
    text: str,
    user_name: str = "Пользователь",
    message_id: int = 0
) -> bool:
    """
    Проверяет сообщение и отправляет уведомление при совпадении.
    
    Returns:
        bool: True если отправлено уведомление
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
