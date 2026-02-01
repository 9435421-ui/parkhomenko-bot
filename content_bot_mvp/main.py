# bot.py
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import os
from dotenv import load_dotenv
from openai import OpenAI
import schedule
import time
import threading
import sqlite3
from datetime import datetime
import asyncio
import sys

# Добавляем корень проекта в путь для импорта сервисов
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.vk_service import vk_service

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "-1003370698977"))
THREAD_ID_KVARTIRY = int(os.getenv("THREAD_ID_KVARTIRY", "2"))
THREAD_ID_KOMMERCIA = int(os.getenv("THREAD_ID_KOMMERCIA", "5"))
THREAD_ID_DOMA = int(os.getenv("THREAD_ID_DOMA", "8"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("BOT_TOKEN and OPENAI_API_KEY must be set in .env")

OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

user_leads = {}

# ==========================
# Настройки бота и OpenAI
# ==========================

# ==========================
# Инициализация бота
# ==========================
bot = telebot.TeleBot(BOT_TOKEN)

# ==========================
# Контент-план
# ==========================
POSTS_FILE = "posts.json"


def load_posts():
    try:
        with open(POSTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except BaseException:
        return []


def save_posts(posts):
    with open(POSTS_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

# ==========================
# Функции генерации контента
# ==========================


def generate_text(prompt: str) -> str:
    try:
        resp = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"Ошибка генерации текста: {e}"


def generate_image(prompt: str) -> str:
    try:
        resp = client.images.generate(
            model="openai/dall-e-3",
            prompt=prompt,
            size="1024x1024"
        )
        return resp.data[0].url
    except Exception as e:
        return f"Ошибка генерации изображения: {e}"


def generate_video(prompt: str) -> str:
    return "Генерация видео временно недоступна."

# ==========================
# База данных лидов
# ==========================
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "parkhomenko_bot.db")


def save_lead_to_db(user_id, source_bot, lead_data):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Убедимся, что таблицы существуют
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS unified_leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                source_bot TEXT NOT NULL,
                lead_type TEXT,
                name TEXT,
                username TEXT,
                phone TEXT,
                extra_contact TEXT,
                details TEXT,
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        details = json.dumps(lead_data, ensure_ascii=False)
        cursor.execute("""
            INSERT INTO unified_leads (user_id, source_bot, lead_type, name, phone, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, source_bot, 'direct_request', lead_data.get('name'), lead_data.get('phone'), details))

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Ошибка сохранения лида в БД: {e}")

# ==========================
# Отправка лидов в группу
# ==========================


def send_lead_to_group(summary_text: str, object_type: str, is_new: bool = True, user_id=None, lead_data=None):
    if object_type == "квартира":
        thread_id = THREAD_ID_KVARTIRY
    elif object_type == "коммерция":
        thread_id = THREAD_ID_KOMMERCIA
    elif object_type == "дом":
        thread_id = THREAD_ID_DOMA
    else:
        thread_id = None

    prefix = "🔥 НОВЫЙ ЛИД" if is_new else "🔄 Обновление лида"

    bot.send_message(
        chat_id=LEADS_GROUP_CHAT_ID,
        text=f"{prefix}\n\n{summary_text}",
        message_thread_id=thread_id
    )

    if user_id and lead_data:
        save_lead_to_db(user_id, "content_bot", lead_data)

# ==========================
# Автопостинг по расписанию
# ==========================


def post_scheduler():
    posts = load_posts()
    if posts:
        post = posts.pop(0)
        save_posts(posts)
        text = generate_text(post["text"])
        img_url = generate_image(post["image"]) if "image" in post else None
        video_url = generate_video(post["video"]) if "video" in post else None

        msg = text
        if img_url:
            msg += f"\n\nИзображение: {img_url}"
        if video_url:
            msg += f"\n\nВидео: {video_url}"

        # Публикация в Telegram
        bot.send_message(CHANNEL_ID, msg)

        # Дублирование в VK (если настроено)
        if os.getenv("VK_API_TOKEN"):
            try:
                # Т.к. мы в отдельном потоке threading, создаем новый loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                attachments = []
                if img_url:
                    attachments.append(img_url)

                loop.run_until_complete(vk_service.send_to_community(msg, attachments))
                loop.close()
            except Exception as e:
                print(f"Ошибка дублирования в VK: {e}")


# Запускаем автопостинг в 12:00 каждый день
schedule.every().day.at("12:00").do(post_scheduler)


def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(10)


threading.Thread(target=run_schedule, daemon=True).start()

# ==========================
# Меню бота
# ==========================


@bot.message_handler(commands=["start"])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Создать пост", callback_data="create_post"))
    markup.add(InlineKeyboardButton("Просмотреть контент-план", callback_data="view_plan"))
    markup.add(InlineKeyboardButton("Репортажный режим (Фото + ИИ)", callback_data="report_mode"))
    markup.add(InlineKeyboardButton("Генерация изображения", callback_data="gen_image"))
    markup.add(InlineKeyboardButton("Генерация видео", callback_data="gen_video"))
    markup.add(InlineKeyboardButton("Собрать лид", callback_data="collect_lead"))
    bot.send_message(message.chat.id, "Привет! Выберите действие:", reply_markup=markup)

# ==========================
# Обработка кнопок
# ==========================


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "create_post":
        bot.send_message(call.message.chat.id, "Отправьте текст поста:")
        bot.register_next_step_handler(call.message, add_post)
    elif call.data == "view_plan":
        posts = load_posts()
        if posts:
            msg = "\n\n".join([p["text"] for p in posts])
            bot.send_message(call.message.chat.id, msg)
        else:
            bot.send_message(call.message.chat.id, "Контент-план пуст.")
    elif call.data == "gen_image":
        bot.send_message(call.message.chat.id, "Введите описание изображения:")
        bot.register_next_step_handler(call.message, generate_image_handler)
    elif call.data == "report_mode":
        bot.send_message(call.message.chat.id, "Пришлите фото с объекта, и я составлю описание для поста.")
        bot.register_next_step_handler(call.message, handle_report_photo)
    elif call.data == "gen_video":
        bot.send_message(call.message.chat.id, "Введите описание видео:")
        bot.register_next_step_handler(call.message, generate_video_handler)
    elif call.data == "approve_report":
        data = user_leads.get(call.message.chat.id)
        if data:
            posts = load_posts()
            posts.append({
                "text": data["temp_text"],
                "file_id": data["temp_file_id"],
                "status": "scheduled"
            })
            save_posts(posts)
            bot.send_message(call.message.chat.id, "Пост запланирован!")
            del user_leads[call.message.chat.id]
        else:
            bot.send_message(call.message.chat.id, "Ошибка: данные не найдены.")
    elif call.data == "edit_report":
        bot.send_message(call.message.chat.id, "Введите новый текст для поста:")
        bot.register_next_step_handler(call.message, update_report_text)
    elif call.data == "collect_lead":
        bot.send_message(call.message.chat.id, "Соглашаетесь ли вы на обработку персональных данных? (да/нет)")
        bot.register_next_step_handler(call.message, ask_name)
    elif call.data.startswith("obj_"):
        object_type = call.data.replace("obj_", "")
        if object_type == "kvartira":
            obj = "квартира"
        elif object_type == "kommertsia":
            obj = "коммерция"
        elif object_type == "dom":
            obj = "дом"
        user_leads[call.message.chat.id]["object_type"] = obj
        bot.send_message(call.message.chat.id, f"{get_pb(6)}Введите город:")
        bot.register_next_step_handler(call.message, ask_media_step)

def ask_media_step(message):
    user_leads[message.chat.id]["city"] = message.text
    bot.send_message(
        message.chat.id,
        f"{get_pb(7)}Прикрепите фото или PDF документов БТИ (или просто напишите «нет», если документов нет):"
    )
    bot.register_next_step_handler(message, finalize_lead)


def add_post(message):
    posts = load_posts()
    posts.append({"text": message.text})
    save_posts(posts)
    bot.send_message(message.chat.id, "Пост добавлен в контент-план!")


def update_report_text(message):
    data = user_leads.get(message.chat.id)
    if data:
        data["temp_text"] = message.text
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Одобрить и запланировать", callback_data="approve_report"))
        bot.send_message(message.chat.id, f"Новый текст:\n\n{message.text}", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "Ошибка сессии.")


def generate_image_handler(message):
    url = generate_image(message.text)
    bot.send_message(message.chat.id, f"Ссылка на изображение: {url}")


def generate_video_handler(message):
    url = generate_video(message.text)
    bot.send_message(message.chat.id, f"Ссылка на видео: {url}")


def handle_report_photo(message):
    if not message.photo:
        bot.send_message(message.chat.id, "Пожалуйста, отправьте именно фото.")
        return

    file_id = message.photo[-1].file_id
    bot.send_message(message.chat.id, "Принял фото. Опишите кратко, что на нем происходит (или просто нажмите /skip для авто-генерации):")
    bot.register_next_step_handler(message, process_report_description, file_id)


def process_report_description(message, file_id):
    context = message.text if message.text != "/skip" else "работа на объекте"
    prompt = (
        f"Напиши профессиональный и вовлекающий пост для Telegram-канала компании ТЕРИОН "
        f"(эксперты по перепланировкам). Тема: Репортаж с объекта. Контекст: {context}. "
        f"Стиль: деловой, экспертный, но доступный. Обязательно добавь призыв к действию: "
        f"пройти квиз по ссылке @terion_bot?start=report_mode"
    )

    bot.send_message(message.chat.id, "Генерирую описание...")
    ai_text = generate_text(prompt)

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Одобрить и запланировать", callback_data="approve_report"))
    markup.add(InlineKeyboardButton("✏️ Изменить текст", callback_data="edit_report"))

    # Сохраняем временные данные
    user_leads[message.chat.id] = {
        "temp_text": ai_text,
        "temp_file_id": file_id
    }

    bot.send_photo(message.chat.id, file_id, caption=ai_text, reply_markup=markup)

# ==========================
# Сбор лидов (КВИЗ)
# ==========================

def get_pb(step, total=7):
    return f"📍 Шаг {step} из {total}\n"

def ask_name(message):
    if message.text.lower() not in ["да", "yes"]:
        bot.send_message(message.chat.id, "Без согласия не можем продолжить.")
        return
    user_leads[message.chat.id] = {"pd_agreed": True}
    bot.send_message(message.chat.id, f"{get_pb(1)}Введите ваше имя:")
    bot.register_next_step_handler(message, ask_phone)


def ask_phone(message):
    user_leads[message.chat.id]["name"] = message.text
    bot.send_message(message.chat.id, f"{get_pb(2)}Введите ваш телефон:")
    bot.register_next_step_handler(message, ask_stage)

def ask_stage(message):
    user_leads[message.chat.id]["phone"] = message.text
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Планирую перепланировку", "Уже выполнена")
    bot.send_message(message.chat.id, f"{get_pb(3)}На какой стадии перепланировка?", reply_markup=markup)
    bot.register_next_step_handler(message, ask_area)

def ask_area(message):
    user_leads[message.chat.id]["stage"] = message.text
    bot.send_message(message.chat.id, f"{get_pb(4)}Укажите метраж помещения (кв. м):", reply_markup=telebot.types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, ask_object_type_inline_msg)

def ask_object_type_inline_msg(message):
    user_leads[message.chat.id]["area"] = message.text
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Квартира", callback_data="obj_kvartira"))
    markup.add(InlineKeyboardButton("Коммерция", callback_data="obj_kommertsia"))
    markup.add(InlineKeyboardButton("Дом", callback_data="obj_dom"))
    bot.send_message(message.chat.id, f"{get_pb(5)}Выберите тип объекта:", reply_markup=markup)




def finalize_lead(message):
    # Обработка медиа (фото или PDF)
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
        user_leads[message.chat.id]["bti_status"] = "Загружено фото"
        user_leads[message.chat.id]["bti_file_id"] = file_id
    elif message.document:
        file_id = message.document.file_id
        user_leads[message.chat.id]["bti_status"] = f"Загружен файл: {message.document.file_name}"
        user_leads[message.chat.id]["bti_file_id"] = file_id
    else:
        user_leads[message.chat.id]["bti_status"] = message.text

    lead = user_leads[message.chat.id]

    # Ветвление финального контента
    stage = lead.get('stage', '').lower()
    if "уже выполнена" in stage:
        final_info = "🎁 Для вас подготовлена инструкция по легализации выполненной перепланировки."
    else:
        final_info = "🎁 Мы подготовили для вас чек-лист проекта перепланировки."

    summary = (
        f"🚀 НОВАЯ ЗАЯВКА (КВИЗ)\n\n"
        f"👤 Имя: {lead.get('name')}\n"
        f"📱 Телефон: {lead.get('phone')}\n"
        f"🏗 Стадия: {lead.get('stage')}\n"
        f"📏 Метраж: {lead.get('area')} м²\n"
        f"🏙 Город: {lead.get('city')}\n"
        f"🏢 Тип: {lead.get('object_type')}\n"
        f"📎 БТИ: {lead.get('bti_status')}"
    )

    send_lead_to_group(summary, lead.get("object_type", "дом"), user_id=message.chat.id, lead_data=lead)

    bot.send_message(
        message.chat.id,
        f"✅ Спасибо! Информация получена.\n\n{final_info}\n\nНаш эксперт свяжется с вами в ближайшее время."
    )
    del user_leads[message.chat.id]


# ==========================
# Запуск бота
# ==========================
print("Бот запущен...")
bot.polling(non_stop=True)
