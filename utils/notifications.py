"""
Модуль для отправки уведомлений админам
"""
import json
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_ID

async def notify_admin_new_lead(bot: Bot, lead_id: int, lead_data: dict):
    """Отправка уведомления админу о новом лиде (в личку)"""

    details = lead_data.get('details', '')
    formatted_details = ""

    if isinstance(details, str) and details.startswith('{'):
        try:
            details_dict = json.loads(details)
            # Убираем уже известные поля
            skip_fields = ['consent', 'consent_date', 'name', 'phone', 'username', 'user_id', '_payload']
            formatted_details = "\n".join([f"• <b>{k}:</b> {v}" for k, v in details_dict.items() if k not in skip_fields])
        except:
            formatted_details = details
    elif isinstance(details, dict):
        skip_fields = ['consent', 'consent_date', 'name', 'phone', 'username', 'user_id', '_payload']
        formatted_details = "\n".join([f"• <b>{k}:</b> {v}" for k, v in details.items() if k not in skip_fields])
    else:
        formatted_details = details

    source = lead_data.get('source_bot', 'unknown')
    lead_type = lead_data.get('lead_type', 'unknown')

    # Красивые названия для типов
    types_map = {
        'initial_contact': '📱 Первичный контакт',
        'quiz_completed': '✅ Квиз завершен',
        'quiz': '📝 В процессе квиза'
    }
    type_display = types_map.get(lead_type, lead_type)

    text = (
        f"🔔 <b>НОВЫЙ ЛИД #{lead_id}</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 <b>Имя:</b> {lead_data.get('name')}\n"
        f"📞 <b>Телефон:</b> <code>{lead_data.get('phone')}</code>\n"
        f"🆔 <b>TG ID:</b> <code>{lead_data.get('user_id')}</code>\n"
        f"🤖 <b>Бот:</b> {source}\n"
        f"📝 <b>Тип:</b> {type_display}\n"
        f"━━━━━━━━━━━━━━━\n"
    )

    if formatted_details:
        text += f"📋 <b>Данные:</b>\n{formatted_details}\n"
        text += f"━━━━━━━━━━━━━━━\n"

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать клиенту", url=f"tg://user?id={lead_data.get('user_id')}")],
        [InlineKeyboardButton(text="⚡️ В работу", callback_data=f"admin:lead_status:{lead_id}:in_progress")]
    ])

    try:
        await bot.send_message(ADMIN_ID, text, reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        print(f"⚠️ Ошибка уведомления админа {ADMIN_ID}: {e}")
