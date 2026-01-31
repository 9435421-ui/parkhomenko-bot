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

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "-1003370698977"))
THREAD_ID_KVARTIRY = int(os.getenv("THREAD_ID_KVARTIRY", "2"))
THREAD_ID_KOMMERCIA = int(os.getenv("THREAD_ID_KOMMERCIA", "5"))
THREAD_ID_DOMA = int(os.getenv("THREAD_ID_DOMA", "8"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("BOT_TOKEN and OPENAI_API_KEY must be set in .env")

client = OpenAI(api_key=OPENAI_API_KEY, base_url="https://openrouter.ai/api/v1")

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
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024"
        )
        return resp.data[0].url
    except Exception as e:
        return f"Ошибка генерации изображения: {e}"


def generate_video(prompt: str) -> str:
    return "Генерация видео временно недоступна."

# ==========================
# Отправка лидов в группу
# ==========================


def send_lead_to_group(summary_text: str, object_type: str, is_new: bool = True):
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

        bot.send_message(CHANNEL_ID, msg)


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
    elif call.data == "gen_video":
        bot.send_message(call.message.chat.id, "Введите описание видео:")
        bot.register_next_step_handler(call.message, generate_video_handler)
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
        bot.send_message(call.message.chat.id, "Введите город:")
        bot.register_next_step_handler(call.message, ask_address)


def add_post(message):
    posts = load_posts()
    posts.append({"text": message.text})
    save_posts(posts)
    bot.send_message(message.chat.id, "Пост добавлен в контент-план!")


def generate_image_handler(message):
    url = generate_image(message.text)
    bot.send_message(message.chat.id, f"Ссылка на изображение: {url}")


def generate_video_handler(message):
    url = generate_video(message.text)
    bot.send_message(message.chat.id, f"Ссылка на видео: {url}")

# ==========================
# Сбор лидов
# ==========================


def ask_name(message):
    if message.text.lower() not in ["да", "yes"]:
        bot.send_message(message.chat.id, "Без согласия не можем продолжить.")
        return
    user_leads[message.chat.id] = {"pd_agreed": True}
    bot.send_message(message.chat.id, "Введите ваше имя:")
    bot.register_next_step_handler(message, ask_phone)


def ask_phone(message):
    user_leads[message.chat.id]["name"] = message.text
    bot.send_message(message.chat.id, "Введите ваш телефон:")
    bot.register_next_step_handler(message, ask_object_type_inline)


def ask_object_type_inline(message):
    user_leads[message.chat.id]["phone"] = message.text
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Квартира", callback_data="obj_kvartira"))
    markup.add(InlineKeyboardButton("Коммерция", callback_data="obj_kommertsia"))
    markup.add(InlineKeyboardButton("Дом", callback_data="obj_dom"))
    bot.send_message(message.chat.id, "Выберите тип объекта:", reply_markup=markup)


def ask_address(message):
    user_leads[message.chat.id]["city"] = message.text
    bot.send_message(
        message.chat.id,
        "Кратко опишите, что хотите изменить в перепланировке "
        "(объединить комнаты, перенести санузел, расширить кухню и т.п.)."
    )
    bot.register_next_step_handler(message, ask_params)


def ask_params(message):
    user_leads[message.chat.id]["change_plan"] = message.text
    bot.send_message(
        message.chat.id,
        "Есть ли сейчас у вас на руках документы БТИ по этому объекту "
        "(поэтажный план, экспликация, техпаспорт)? "
        "Кратко опишите: есть/нет, в каком виде."
    )
    bot.register_next_step_handler(message, finalize_lead)


def finalize_lead(message):
    user_leads[message.chat.id]["bti_status"] = message.text
    lead = user_leads[message.chat.id]
    summary = (
        f"Имя: {lead.get('name')}\n"
        f"Телефон: {lead.get('phone')}\n"
        f"Тип объекта: {lead.get('object_type')}\n"
        f"Город/регион: {lead.get('city')}\n"
        f"Что хочет изменить: {lead.get('change_plan')}\n"
        f"Статус документов БТИ: {lead.get('bti_status')}"
    )
    send_lead_to_group(summary, lead["object_type"])
    bot.send_message(
        message.chat.id,
        "Спасибо, информация получена. Лид отправлен специалисту. "
        "Адрес и детали по документам уточним уже на следующем шаге общения."
    )
    del user_leads[message.chat.id]


# ==========================
# Запуск бота
# ==========================
print("Бот запущен...")
bot.polling(non_stop=True)

