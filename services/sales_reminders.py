"""
Автоматические напоминания для продажных диалогов (дожим).

Проверяет беседы, где клиент остановился на шаге 3 (документ не получен),
и отправляет мягкие напоминания через 24 часа и 3 дня.
"""
import logging
from datetime import datetime, timedelta
from aiogram import Bot

from database import db
from handlers.sales_agent import sales_agent
from config import BOT_TOKEN

logger = logging.getLogger(__name__)


async def send_sales_reminders():
    """
    Задача APScheduler: проверяет беседы для напоминаний и отправляет их.
    Запускается каждые 6 часов.
    """
    try:
        await db.connect()
        
        # Проверяем беседы для напоминания через 24 часа
        conversations_24h = await db.get_conversations_for_reminder(hours=24)
        
        # Проверяем беседы для напоминания через 3 дня (72 часа)
        conversations_3d = await db.get_conversations_for_reminder(hours=72)
        
        if not conversations_24h and not conversations_3d:
            logger.debug("Нет бесед для напоминаний")
            return
        
        bot = Bot(token=BOT_TOKEN)
        
        sent_24h = 0
        sent_3d = 0
        
        # Отправляем напоминания через 24 часа
        for conv in conversations_24h:
            last_reminder = conv.get("last_reminder_at")
            if last_reminder:
                continue  # Уже отправляли напоминание
            
            reminder_text = await sales_agent.send_reminder(conv, "24h")
            if reminder_text:
                try:
                    user_id = conv.get("user_id")
                    if user_id:
                        await bot.send_message(user_id, reminder_text, parse_mode="HTML")
                        sent_24h += 1
                        logger.info(f"Напоминание 24ч отправлено пользователю {user_id}")
                except Exception as e:
                    logger.warning(f"Не удалось отправить напоминание 24ч пользователю {conv.get('user_id')}: {e}")
        
        # Отправляем напоминания через 3 дня
        for conv in conversations_3d:
            reminder_text = await sales_agent.send_reminder(conv, "3days")
            if reminder_text:
                try:
                    user_id = conv.get("user_id")
                    if user_id:
                        await bot.send_message(user_id, reminder_text, parse_mode="HTML")
                        sent_3d += 1
                        logger.info(f"Напоминание 3д отправлено пользователю {user_id}")
                except Exception as e:
                    logger.warning(f"Не удалось отправить напоминание 3д пользователю {conv.get('user_id')}: {e}")
        
        if sent_24h > 0 or sent_3d > 0:
            logger.info(f"✅ Напоминания отправлены: 24ч={sent_24h}, 3д={sent_3d}")
        
        await bot.session.close()
        
    except Exception as e:
        logger.exception("Ошибка при отправке напоминаний: %s", e)
