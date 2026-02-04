"""
Админский интерфейс для управления лидами
"""
import csv
import io
import os
from aiogram import Router, F, Bot
from aiogram.types import Message, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from config import ADMIN_ID
from database.db import db

router = Router()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return

    stats = await db.get_stats()

    text = (
        "📊 <b>Статистика ТЕРИОН Mini-CRM</b>\n\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"📝 Начали квиз: {stats['quiz_started']}\n"
        f"📞 Оставили контакт: {stats['contacts_left']}\n"
        f"✅ Завершили квиз: {stats['quiz_completed']}\n\n"
        f"🆕 Новые лиды: {stats['status_new']}\n"
        f"⚡️ В работе: {stats['status_progress']}\n\n"
        "Используйте кнопки ниже для управления:"
    )

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Выгрузить лиды (CSV)", callback_data="admin:export_csv")],
        [InlineKeyboardButton(text="🔄 Обновить статистику", callback_data="admin:refresh_stats")]
    ])

    await message.answer(text, reply_markup=markup, parse_mode="HTML")

@router.callback_query(F.data == "admin:refresh_stats")
async def refresh_stats(callback):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа", show_alert=True)
        return

    stats = await db.get_stats()
    text = (
        "📊 <b>Статистика ТЕРИОН Mini-CRM</b>\n\n"
        f"👥 Всего пользователей: {stats['total_users']}\n"
        f"📝 Начали квиз: {stats['quiz_started']}\n"
        f"📞 Оставили контакт: {stats['contacts_left']}\n"
        f"✅ Завершили квиз: {stats['quiz_completed']}\n\n"
        f"🆕 Новые лиды: {stats['status_new']}\n"
        f"⚡️ В работе: {stats['status_progress']}\n\n"
        "Используйте кнопки ниже для управления:"
    )

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Выгрузить лиды (CSV)", callback_data="admin:export_csv")],
        [InlineKeyboardButton(text="🔄 Обновить статистику", callback_data="admin:refresh_stats")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data == "admin:export_csv")
async def export_leads_csv(callback):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа", show_alert=True)
        return

    leads = await db.get_all_unified_leads()

    if not leads:
        await callback.answer("Лидов пока нет", show_alert=True)
        return

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=leads[0].keys())
    writer.writeheader()
    writer.writerows(leads)

    csv_data = output.getvalue().encode('utf-8-sig')
    file = BufferedInputFile(csv_data, filename="terion_leads.csv")

    await callback.message.answer_document(file, caption="📂 Полная выгрузка лидов ТЕРИОН")
    await callback.answer()

@router.callback_query(F.data.startswith("admin:lead_status:"))
async def change_lead_status(callback):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет доступа", show_alert=True)
        return

    parts = callback.data.split(":")
    lead_id = int(parts[2])
    new_status = parts[3]

    # Здесь можно добавить метод в БД для обновления статуса
    async with db.conn.cursor() as cursor:
        await cursor.execute("UPDATE unified_leads SET status = ? WHERE id = ?", (new_status, lead_id))
        await db.conn.commit()

    status_text = "В работе" if new_status == "in_progress" else "Завершен"

    await callback.answer(f"Статус лида #{lead_id} изменен на '{status_text}'")

    # Обновляем сообщение (убираем кнопку "В работу" или меняем её)
    markup = callback.message.reply_markup
    # Просто для примера, можно усложнить
    await callback.message.edit_reply_markup(reply_markup=None)
