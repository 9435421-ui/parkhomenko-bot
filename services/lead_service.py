import sqlite3
from datetime import datetime
from config import LEADS_GROUP_CHAT_ID, THREAD_ID_KVARTIRY, THREAD_ID_KOMMERCIA, THREAD_ID_DOMA

def send_lead_to_group(summary_text, object_type, is_new=True):
    # Сохранение в БД
    conn = sqlite3.connect("parkhomenko_bot.db")
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO unified_leads (tg_id, username, full_name, phone, property_type, stage, area, source, bot_label)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        None,  # tg_id
        None,  # username
        None,  # full_name
        None,  # phone
        object_type,
        "планируется",  # stage
        None,  # area
        "ИИ-консультант",  # source
        "ТЕРИОН"  # bot_label
    ))

    conn.commit()
    conn.close()

    # Отправка в Telegram
    thread_id = None
    if object_type == "квартира":
        thread_id = THREAD_ID_KVARTIRY
    elif object_type == "коммерция":
        thread_id = THREAD_ID_KOMMERCIA
    elif object_type == "дом":
        thread_id = THREAD_ID_DOMA

    prefix = "🔥 НОВЫЙ ЛИД" if is_new else "🔄 Обновление лида"

    message = f"{prefix}\n\n{summary_text}\n\n🤖 Обработано ИИ-консультантом системы ТЕРИОН"

    # Заглушка для отправки (требуется реальный бот)
    print(f"Отправка в группу {LEADS_GROUP_CHAT_ID}, thread_id={thread_id}:")
    print(message)
