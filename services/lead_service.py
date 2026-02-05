"""
Сервис для маршрутизации и отправки заявок (лидов)
"""
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import LEADS_GROUP_CHAT_ID, THREAD_ID_KVARTIRY, THREAD_ID_KOMMERCIA, THREAD_ID_DOMA, THREAD_ID_LOGS

async def send_lead_to_admin_group(bot: Bot, lead_data: dict):
    """
    Отправка заявки в админ-группу с маршрутизацией по топикам
    """
    obj_type = lead_data.get('obj_type', '').lower()
    
    # Маршрутизация по топикам
    if 'квартира' in obj_type:
        thread_id = THREAD_ID_KVARTIRY
    elif 'коммерция' in obj_type:
        thread_id = THREAD_ID_KOMMERCIA
    elif 'дом' in obj_type:
        thread_id = THREAD_ID_DOMA
    else:
        thread_id = THREAD_ID_LOGS

    user_id = lead_data.get('user_id')
    username = lead_data.get('username') or "Нет"
    phone = lead_data.get('phone') or "Нет"
    
    # Формируем текст CRM-карточки
    text = (
        f"🆕 <b>НОВАЯ ЗАЯВКА ТЕРИОН</b>\n\n"
        f"👤 <b>Клиент:</b> {lead_data.get('name')}\n"
        f"📱 <b>Телефон:</b> <code>{phone}</code>\n"
        f"🆔 <b>TG ID:</b> <code>{user_id}</code>\n"
        f"🔗 <b>Username:</b> @{username}\n\n"
        f"🏙 <b>Город:</b> {lead_data.get('city')}\n"
        f"🏢 <b>Тип:</b> {lead_data.get('obj_type')}\n"
        f"🏠 <b>Этаж:</b> {lead_data.get('floor_info')}\n"
        f"📐 <b>Площадь:</b> {lead_data.get('area')} кв.м\n"
        f"🏗 <b>Статус:</b> {lead_data.get('status')}\n"
        f"📝 <b>Описание:</b> {lead_data.get('changes_desc', 'Нет')}\n"
        f"📂 <b>План:</b> {'Да' if lead_data.get('has_plan') else 'Нет'}\n"
    )

    # Кнопка связи
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Связаться с клиентом", url=f"tg://user?id={user_id}")]
    ])

    try:
        if lead_data.get('plan_file_id'):
            await bot.send_document(
                chat_id=LEADS_GROUP_CHAT_ID,
                document=lead_data.get('plan_file_id'),
                caption=text,
                parse_mode="HTML",
                message_thread_id=thread_id,
                reply_markup=markup
            )
        else:
            await bot.send_message(
                chat_id=LEADS_GROUP_CHAT_ID,
                text=text,
                parse_mode="HTML",
                message_thread_id=thread_id,
                reply_markup=markup
            )
    except Exception as e:
        print(f"❌ Ошибка отправки заявки в группу: {e}")

async def send_contact_to_logs(bot: Bot, user_data: dict):
    """
    Отправка первичного контакта в топик Логи (88)
    """
    user_id = user_data.get('user_id')
    name = user_data.get('name')
    phone = user_data.get('phone')

    text = (
        f"📱 <b>ПОЛУЧЕН КОНТАКТ</b>\n\n"
        f"👤 <b>Имя:</b> {name}\n"
        f"📱 <b>Телефон:</b> <code>{phone}</code>\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>"
    )

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать", url=f"tg://user?id={user_id}")]
    ])

    try:
        await bot.send_message(
            chat_id=LEADS_GROUP_CHAT_ID,
            text=text,
            parse_mode="HTML",
            message_thread_id=THREAD_ID_LOGS,
            reply_markup=markup
        )
    except Exception as e:
        print(f"❌ Ошибка отправки контакта в логи: {e}")
