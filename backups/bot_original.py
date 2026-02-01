# bot.py
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import openai
import schedule
import time
import threading

# ==========================
# Настройки бота и OpenAI
# ==========================
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
CHANNEL_ID = "YOUR_CHANNEL_ID_HERE"

OPENAI_API_KEY = "YOUR_OPENAI_API_KEY_HERE"
openai.api_key = OPENAI_API_KEY

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


def generate_text(prompt):
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка генерации текста: {e}"


def generate_image(prompt):
    try:
        response = openai.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024"
        )
        return response.data[0].url
    except Exception as e:
        return f"Ошибка генерации изображения: {e}"


def generate_video(prompt):
    try:
        response = openai.video.generate(
            model="gpt-video-1",
            prompt=prompt,
            size="512x512"
        )
        return response.data[0].url
    except Exception as e:
        return f"Ошибка генерации видео: {e}"

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
# Запуск бота
# ==========================
print("Бот запущен...")
bot.polling(non_stop=True)
