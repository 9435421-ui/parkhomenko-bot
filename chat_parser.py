"""
Chat Parser — мониторинг чатов ТСЖ и ЖК через Telethon.
Пересылает сообщения с ключевыми словами в топик 88.
"""
import os
import asyncio
import logging
from telethon import TelegramClient, events
from dotenv import load_dotenv

# Импорт конфигурации
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

# Список чатов для мониторинга (будут добавлены пользователем)
TARGET_CHATS = [
    # Пример: t.me/c/1849161015/1
    # 1849161015 - ID чата
    # 1 - топик (опционально)
]

# Сообщение для пересылки
FORWARD_TEMPLATE = """🔔 <b>Лид из чата ТСЖ/ЖК!</b>

💬 <b>Ключевое слово:</b> {keyword}
📍 <b>Чат:</b> {chat_title}

📝 <b>Сообщение:</b>
{message_text}

🔗 <a href="{message_link}">Открыть в чате</a>

👉 <a href="https://t.me/TERION_KvizBot?start=quiz">КВИЗ</a> | <a href="tg://user?id=unknown">Написать</a>"""


def check_keywords(text: str) -> str | None:
    """
    Проверяет сообщение на наличие ключевых слов.
    Returns: найденное ключевое слово или None
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
    Пересылает сообщение в топик 88 через aiogram бота.
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
        logger.info(f"✅ Лид переслан: {keyword} из {chat_title}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка пересылки: {e}")
        
    finally:
        await bot.session.close()


async def process_message(event):
    """
    Обрабатывает входящее сообщение из чата.
    """
    try:
        # Получаем текст сообщения
        if event.message.text:
            message_text = event.message.text
        elif event.message.message:
            message_text = event.message.message
        else:
            return
        
        # Проверяем на ключевые слова
        keyword = check_keywords(message_text)
        if not keyword:
            return
        
        # Получаем информацию о чате
        chat = await event.get_chat()
        chat_title = getattr(chat, 'title', 'Неизвестный чат')
        
        # Формируем ссылку на сообщение
        chat_id = event.chat_id
        message_id = event.message.id
        
        # Ссылка формата t.me/c/ID/ID
        if str(chat_id).startswith("-100"):
            clean_id = str(chat_id).replace("-100", "")
            message_link = f"https://t.me/c/{clean_id}/{message_id}"
        else:
            message_link = f"https://t.me/{chat.username}/{message_id}" if hasattr(chat, 'username') and chat.username else f"https://t.me/c/{chat_id}/{message_id}"
        
        logger.info(f"🔔 Найден лид! Ключевое слово: {keyword} в чате: {chat_title}")
        
        # Пересылаем в топик 88
        await forward_to_tg(message_text, chat_title, message_link, keyword)
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки сообщения: {e}")


async def start_monitoring():
    """
    Запускает мониторинг чатов.
    """
    logger.info("🚀 Запуск мониторинга чатов ТСЖ/ЖК...")
    
    # Получаем клиент Telethon
    client = await get_client()
    
    if not client:
        logger.error("❌ Не удалось подключиться к Telegram")
        return
    
    logger.info("✅ Подключено к Telegram")
    
    if not TARGET_CHATS:
        logger.warning("⚠️ Список целевых чатов пуст!")
        logger.info("   Добавьте чаты в переменную TARGET_CHATS")
        logger.info("   Пример: TARGET_CHATS = ['https://t.me/c/1849161015/1']")
    
    # Добавляем обработчики для каждого чата
    for chat_url in TARGET_CHATS:
        try:
            # Извлекаем ID чата из ссылки
            # t.me/c/1849161015/1 -> 1849161015
            chat_id = chat_url.replace("https://t.me/c/", "").replace("https://t.me/", "").split("/")[0]
            chat_id = int(chat_id)
            
            # Подписываемся на новые сообщения
            @client.on(events.NewMessage(chats=chat_id))
            async def handler(event):
                await process_message(event)
            
            logger.info(f"✅ Подписан на чат: {chat_url}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка подписки на {chat_url}: {e}")
    
    logger.info("🎉 Мониторинг запущен!")
    logger.info("   Ожидание сообщений...")
    
    # Запускаем клиент (блокирующий вызов)
    await client.run_until_disconnected()


if __name__ == "__main__":
    # Запуск
    asyncio.run(start_monitoring())
