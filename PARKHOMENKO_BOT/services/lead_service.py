"""
Централизованный сервис маршрутизации заявок
"""
import logging
from aiogram import Bot
from config import (
    LEADS_GROUP_CHAT_ID, THREAD_ID_KVARTIRY,
    THREAD_ID_KOMMERCIA, THREAD_ID_DOMA, THREAD_ID_LOGS
)

async def send_lead_to_admin_group(bot: Bot, user_id: int, data: dict, file_id: str = None):
    """Отправка полной анкеты квиза в соответствующий топик"""

    # Определяем топик
    obj_type = data.get("object_type")
    if obj_type == "Квартира":
        thread_id = THREAD_ID_KVARTIRY
    elif obj_type == "Коммерция":
        thread_id = THREAD_ID_KOMMERCIA
    else:
        thread_id = THREAD_ID_DOMA

    # Формируем текст
    text = (
        f"📋 <b>НОВАЯ ЗАЯВКА (Квиз 7 шагов)</b>\n\n"
        f"👤 <b>ID:</b> <code>{user_id}</code>\n"
        f"📍 <b>Город:</b> {data.get('city')}\n"
        f"🏠 <b>Тип:</b> {obj_type}\n"
        f"🏢 <b>Этаж:</b> {data.get('floor')}\n"
        f"📏 <b>Площадь:</b> {data.get('area')} м²\n"
        f"🔧 <b>Статус:</b> {data.get('status')}\n"
        f"📝 <b>Описание:</b> {data.get('description')}\n"
    )

    try:
        if file_id:
            await bot.send_document(
                chat_id=LEADS_GROUP_CHAT_ID,
                document=file_id,
                caption=text,
                message_thread_id=thread_id,
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                chat_id=LEADS_GROUP_CHAT_ID,
                text=text,
                message_thread_id=thread_id,
                parse_mode="HTML"
            )
    except Exception as e:
        logging.error(f"Error sending lead to admin: {e}")

async def send_contact_to_logs(bot: Bot, user_id: int, name: str, phone: str):
    """Отправка первичного контакта в лог-ветку"""
    text = (
        f"📞 <b>ПОЛУЧЕН КОНТАКТ</b>\n\n"
        f"👤 <b>Имя:</b> {name}\n"
        f"📱 <b>Телефон:</b> {phone}\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"🔗 <a href='tg://user?id={user_id}'>Связаться с клиентом</a>"
    )

    try:
        await bot.send_message(
            chat_id=LEADS_GROUP_CHAT_ID,
            text=text,
            message_thread_id=THREAD_ID_LOGS,
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Error sending contact to logs: {e}")
