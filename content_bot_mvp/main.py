# bot.py
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import re
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

load_dotenv()

# Добавляем корень проекта в путь для импорта сервисов
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.vk_service import vk_service
from utils.voice_handler import voice_handler

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
    except Exception:
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

        # Проверяем наличие активного лида за последние 24 часа
        cursor.execute(
            """SELECT id FROM unified_leads
               WHERE user_id = ? AND source_bot = ?
               AND created_at > datetime('now', '-1 day')
               ORDER BY created_at DESC LIMIT 1""",
            (user_id, source_bot)
        )
        row = cursor.fetchone()

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
                consent INTEGER DEFAULT 0,
                consent_date TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)

        details = json.dumps(lead_data, ensure_ascii=False)

        if row:
            lead_id = row[0]
            # Обновляем существующий лид
            update_data = {
                "name": lead_data.get('name'),
                "phone": lead_data.get('phone'),
                "details": details,
                "lead_type": "quiz_completed" if "area" in lead_data else "initial_contact"
            }
            if lead_data.get("consent"):
                update_data["consent"] = 1
                update_data["consent_date"] = lead_data.get("consent_date")

            set_clause = ", ".join([f"{k} = ?" for k in update_data.keys()])
            values = list(update_data.values()) + [lead_id]
            cursor.execute(f"UPDATE unified_leads SET {set_clause} WHERE id = ?", values)
        else:
            # Вставляем новый
            cursor.execute("""
                INSERT INTO unified_leads (user_id, source_bot, lead_type, name, phone, details, consent, consent_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                source_bot,
                'initial_contact',
                lead_data.get('name'),
                lead_data.get('phone'),
                details,
                1 if lead_data.get("consent") else 0,
                lead_data.get("consent_date")
            ))

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

    try:
        bot.send_message(
            chat_id=LEADS_GROUP_CHAT_ID,
            text=f"{prefix}\n\n{summary_text}",
            message_thread_id=thread_id
        )
    except Exception as e:
        print(f"Ошибка отправки лида в группу {LEADS_GROUP_CHAT_ID}: {e}")
        # Попытка отправить без thread_id
        try:
            bot.send_message(chat_id=LEADS_GROUP_CHAT_ID, text=f"{prefix}\n\n{summary_text}")
        except Exception as e2:
            print(f"Критическая ошибка отправки лида: {e2}")

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
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Я согласен и хочу продолжить", callback_data="consent_quiz"))
        bot.send_message(
            call.message.chat.id,
            "Для начала работы необходимо ваше согласие на обработку персональных данных.",
            reply_markup=markup
        )
    elif call.data == "consent_quiz":
        user_leads[call.message.chat.id] = {"consent": True, "consent_date": datetime.now().isoformat()}
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(telebot.types.KeyboardButton("📱 Поделиться контактом", request_contact=True))
        bot.send_message(
            call.message.chat.id,
            "Спасибо! Пожалуйста, поделитесь вашим контактом для сохранения заявки.",
            reply_markup=markup
        )
        # Следующий шаг обработает специальный хендлер для контактов
    elif call.data.startswith("obj_"):
        object_type = call.data.replace("obj_", "")
        if object_type == "kvartira":
            obj = "квартира"
        elif object_type == "kommertsia":
            obj = "коммерция"
        elif object_type == "dom":
            obj = "дом"
        user_leads[call.message.chat.id]["object_type"] = obj

        # Переходим к вопросу про этаж
        ask_floor_step(call.message.chat.id)




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

def get_pb(step, total=10):
    return f"📍 Шаг {step} из {total}\n"


def get_message_text(message):
    """Извлекает текст из сообщения или транскрибирует голос"""
    if message.voice:
        try:
            file_info = bot.get_file(message.voice.file_id)
            downloaded_file = bot.download_file(file_info.file_path)

            # Временный файл
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".oga", delete=False) as temp:
                temp.write(downloaded_file)
                temp_path = temp.name

            text = voice_handler.transcribe(temp_path)
            os.unlink(temp_path)

            if text:
                bot.send_message(message.chat.id, f"🎤 Распознано: «{text}»")
                return text
            return ""
        except Exception as e:
            print(f"Ошибка транскрибации в контент-боте: {e}")
            return ""
    return message.text if message.text else ""


def ask_city_step(message):
    role = get_message_text(message)
    if not role:
        bot.send_message(message.chat.id, "Пожалуйста, укажите вашу роль.")
        bot.register_next_step_handler(message, ask_city_step)
        return
    user_leads[message.chat.id]["role"] = role
    name = user_leads[message.chat.id].get("name", "")
    bot.send_message(message.chat.id, f"{get_pb(2)}{name}, из какого вы города?")
    bot.register_next_step_handler(message, ask_obj_type_step)

def ask_obj_type_step(message):
    city = get_message_text(message)
    if not city:
        bot.send_message(message.chat.id, "Пожалуйста, укажите город.")
        bot.register_next_step_handler(message, ask_obj_type_step)
        return
    user_leads[message.chat.id]["city"] = city
    name = user_leads[message.chat.id].get("name", "")
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Квартира", callback_data="obj_kvartira"))
    markup.add(InlineKeyboardButton("Коммерция", callback_data="obj_kommertsia"))
    markup.add(InlineKeyboardButton("Дом", callback_data="obj_dom"))
    bot.send_message(message.chat.id, f"{get_pb(3)}{name}, выберите тип объекта:", reply_markup=markup)

def ask_floor_step(message_or_id):
    # Этот метод вызывается из callback_handler
    chat_id = message_or_id if isinstance(message_or_id, int) else message_or_id.chat.id
    name = user_leads[chat_id].get("name", "")
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Не первый / не последний")
    markup.add("Первый", "Последний")

    bot.send_message(
        chat_id,
        f"{get_pb(4)}{name}, укажите этаж и этажность (например: 5/17) или выберите вариант:",
        reply_markup=markup
    )
    # Используем фейковое сообщение для bot.register_next_step_handler если нужно
    # Но проще вызвать его отсюда
    bot.register_next_step_handler_by_chat_id(chat_id, ask_area_step)

def ask_area_step(message):
    floor = get_message_text(message)
    if not floor:
        bot.send_message(message.chat.id, "Укажите этаж.")
        bot.register_next_step_handler(message, ask_area_step)
        return
    user_leads[message.chat.id]["floor"] = floor
    name = user_leads[message.chat.id].get("name", "")
    bot.send_message(message.chat.id, f"{get_pb(5)}{name}, укажите метраж помещения (кв. м, только число):", reply_markup=telebot.types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, ask_status_step)

def ask_status_step(message):
    area = get_message_text(message)
    if not area or not re.match(r'^\d+([.,]\d+)?$', area.strip()):
        bot.send_message(message.chat.id, "Пожалуйста, введите метраж числом (например: 45).")
        bot.register_next_step_handler(message, ask_status_step)
        return
    user_leads[message.chat.id]["area"] = area.replace(',', '.')
    name = user_leads[message.chat.id].get("name", "")
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Планирую перепланировку", "Уже выполнена")
    bot.send_message(message.chat.id, f"{get_pb(6)}{name}, на какой стадии перепланировка?", reply_markup=markup)
    bot.register_next_step_handler(message, ask_complexity_step)

def ask_complexity_step(message):
    stage = get_message_text(message)
    if not stage:
        bot.send_message(message.chat.id, "Пожалуйста, выберите стадию.")
        bot.register_next_step_handler(message, ask_complexity_step)
        return
    user_leads[message.chat.id]["stage"] = stage
    name = user_leads[message.chat.id].get("name", "")
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Стены", "Мокрые зоны")
    markup.add("Нет")
    bot.send_message(message.chat.id, f"{get_pb(7)}{name}, есть ли сложные зоны (несущие стены, мокрые зоны)?", reply_markup=markup)
    bot.register_next_step_handler(message, ask_goal_step)

def ask_goal_step(message):
    complexity = get_message_text(message)
    user_leads[message.chat.id]["complexity"] = complexity
    name = user_leads[message.chat.id].get("name", "")
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Инвест", "Для жизни")
    bot.send_message(message.chat.id, f"{get_pb(8)}{name}, какова цель перепланировки?", reply_markup=markup)
    bot.register_next_step_handler(message, ask_bti_step)


def ask_bti_step(message):
    goal = get_message_text(message)
    if not goal:
        bot.send_message(message.chat.id, "Пожалуйста, выберите цель.")
        bot.register_next_step_handler(message, ask_bti_step)
        return
    user_leads[message.chat.id]["goal"] = goal
    name = user_leads[message.chat.id].get("name", "")

    bot.send_message(
        message.chat.id,
        f"{get_pb(9)}{name}, прикрепите фото или PDF документов БТИ (или просто напишите «нет», если документов нет):",
        reply_markup=telebot.types.ReplyKeyboardRemove()
    )
    bot.register_next_step_handler(message, ask_urgency_step)


def ask_urgency_step(message):
    # Проверка на медиа
    if message.content_type in ['photo', 'document']:
        user_leads[message.chat.id]["bti_text"] = "Файл/Фото прикреплено"
        # В телеботе сохранение file_id для пересылки сложнее в упрощенном ТЗ,
        # но мы пометим текст для админа.
    else:
        bti = get_message_text(message)
        user_leads[message.chat.id]["bti_text"] = bti or "нет"

    name = user_leads[message.chat.id].get("name", "")
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("🔥 Срочно", "📅 В течение месяца")
    markup.add("🔍 Просто прицениваюсь")
    bot.send_message(message.chat.id, f"{get_pb(10)}{name}, когда планируете начинать?", reply_markup=markup)
    bot.register_next_step_handler(message, finalize_lead)


def finalize_lead(message):
    urgency = get_message_text(message)
    user_leads[message.chat.id]["urgency"] = urgency

    lead = user_leads[message.chat.id]

    # Ветвление финального контента
    stage = lead.get('stage', '').lower()
    name = lead.get('name', 'клиент')
    if "уже выполнена" in stage:
        final_text = (
            f"✅ <b>Спасибо, {name}! Ваша заявка принята.</b>\n\n"
            "Так как перепланировка уже выполнена, мы подготовим для вас план легализации:\n"
            "1️⃣ Проверим допустимость выполненных работ.\n"
            "2️⃣ Оценим риски штрафов и предписаний.\n"
            "3️⃣ Подскажем, как узаконить всё без судов.\n\n"
            "Наш эксперт свяжется с вами в ближайшее рабочее время."
        )
    else:
        final_text = (
            f"✅ <b>Спасибо, {name}! Заявка успешно оформлена.</b>\n\n"
            "Для вашей будущей перепланировки мы подготовим:\n"
            "1️⃣ Расчет стоимости проектирования и согласования.\n"
            "2️⃣ Пошаговый алгоритм действий именно для вашего случая.\n"
            "3️⃣ Список необходимых документов БТИ и ЕГРН.\n\n"
            "Эксперт позвонит вам для уточнения деталей."
        )

    summary = (
        f"🚀 ЗАВЕРШЕН КВИЗ (Контент-бот)\n\n"
        f"👤 Имя: {lead.get('name')}\n"
        f"📱 Телефон: {lead.get('phone')}\n"
        f"🏙 Город: {lead.get('city')}\n"
        f"🏗 Стадия: {lead.get('stage')}\n"
        f"🏢 Тип: {lead.get('object_type')}\n"
        f"🏢 Этаж: {lead.get('floor')}\n"
        f"📏 Метраж: {lead.get('area')} м²\n"
        f"🧱 Сложность: {lead.get('complexity')}\n"
        f"🎯 Цель: {lead.get('goal')}\n"
        f"📂 БТИ: {lead.get('bti_text')}\n"
        f"⏳ Срочность: {lead.get('urgency')}"
    )

    send_lead_to_group(summary, lead.get("object_type", "дом"), user_id=message.chat.id, lead_data=lead)

    bot.send_message(
        message.chat.id,
        final_text,
        parse_mode="HTML",
        reply_markup=telebot.types.ReplyKeyboardRemove()
    )
    del user_leads[message.chat.id]


@bot.message_handler(content_types=["contact"])
def handle_contact_quiz(message):
    if message.chat.id in user_leads and user_leads[message.chat.id].get("consent"):
        phone = message.contact.phone_number
        name = message.from_user.full_name
        user_id = message.chat.id

        user_leads[user_id]["phone"] = phone
        user_leads[user_id]["name"] = name

        # Сохраняем первичный лид
        try:
            save_lead_to_db(user_id, "content_bot", {
                "name": name,
                "phone": phone,
                "consent": True,
                "consent_date": user_leads[user_id].get("consent_date")
            })
        except Exception as e:
            print(f"ERROR lead_save_failed: {e}")

        # Уведомляем админа
        summary = (
            f"📱 ПОЛУЧЕН КОНТАКТ (Контент-бот)\n\n"
            f"👤 Имя: {name}\n"
            f"📱 Телефон: {phone}\n"
            f"🆔 ID: {user_id}"
        )
        send_lead_to_group(summary, "дом", is_new=True)

        bot.send_message(user_id, f"{get_pb(1)}📋 {name}, кто вы? (Собственник/Дизайнер/Инвестор/Другое):", reply_markup=telebot.types.ReplyKeyboardRemove())
        bot.register_next_step_handler(message, ask_city_step)


@bot.message_handler(content_types=["voice"])
def handle_voice_global(message):
    """Глобальный обработчик голоса для транскрибации вне квиза"""
    text = get_message_text(message)
    if text:
        bot.send_message(message.chat.id, "Я услышал вас. Чем я могу помочь? Используйте меню или кнопки.")


# ==========================
# Запуск бота
# ==========================
print("Бот запущен...")
bot.polling(non_stop=True)
