"""
Content Bot — бот для генерации контента.
Использует Router AI (Kimi/Qwen) и YandexGPT.
"""
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("CONTENT_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003612599428"))
LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "-1003370698977"))
THREAD_ID_KVARTIRY = int(os.getenv("THREAD_ID_KVARTIRY", "2"))
THREAD_ID_KOMMERCIA = int(os.getenv("THREAD_ID_KOMMERCIA", "5"))
THREAD_ID_DOMA = int(os.getenv("THREAD_ID_DOMA", "8"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("CONTENT_BOT_TOKEN must be set in .env")

# Инициализируем ИИ
from utils import router_ai, yandex_gpt

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
    except:
        return []


def save_posts(posts):
    with open(POSTS_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

# ==========================
# Генерация контента через Router AI / YandexGPT
# ==========================


async def generate_text_async(prompt: str) -> str:
    """Генерация текста через Router AI"""
    try:
        result = await router_ai.generate(
            system_prompt="Ты - эксперт по контенту для канала о перепланировках.",
            user_message=prompt
        )
        if result:
            return result
    except Exception as e:
        print(f"Router AI error: {e}")
    
    # Fallback на YandexGPT
    try:
        result = await yandex_gpt.generate(
            system_prompt="Ты - эксперт по контенту.",
            user_message=prompt
        )
        return result or "Ошибка генерации"
    except Exception as e:
        return f"Ошибка: {e}"


def generate_text(prompt: str) -> str:
    """Синхронная обёртка"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(generate_text_async(prompt))
        loop.close()
        return result
    except:
        return "Ошибка генерации текста"


# ==========================
# Генерация изображений через Flux (Router AI)
# ==========================


def generate_image(prompt: str) -> str:
    """Генерация изображения"""
    try:
        from image_gen import generate
        result = generate(prompt)
        return result or "Ошибка генерации изображения"
    except Exception as e:
        return f"Ошибка: {e}"


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
# Меню бота
# ==========================


@bot.message_handler(commands=["start"])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📝 Создать пост", callback_data="create_post"))
    markup.add(InlineKeyboardButton("📋 Контент-план", callback_data="view_plan"))
    markup.add(InlineKeyboardButton("🎨 Сгенерировать картинку", callback_data="gen_image"))
    markup.add(InlineKeyboardButton("💬 Задать вопрос ИИ", callback_data="ask_ai"))
    bot.send_message(
        message.chat.id,
        "🎯 Контент-бот ТЕРИОН\n\n"
        "Выберите действие:",
        reply_markup=markup
    )


# ==========================
# Обработка кнопок
# ==========================


user_leads = {}


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "create_post":
        msg = bot.send_message(call.message.chat.id, "📝 Отправьте тему поста или идею:")
        bot.register_next_step_handler(msg, add_post)
    elif call.data == "view_plan":
        posts = load_posts()
        if posts:
            response = "📋 <b>Контент-план:</b>\n\n"
            for i, post in enumerate(posts[:10], 1):
                response += f"{i}. {post.get('title', 'Без темы')}\n"
            bot.send_message(call.message.chat.id, response, parse_mode="HTML")
        else:
            bot.send_message(call.message.chat.id, "📭 Контент-план пуст.")
    elif call.data == "gen_image":
        msg = bot.send_message(call.message.chat.id, "🎨 Опишите изображение:")
        bot.register_next_step_handler(msg, generate_image_handler)
    elif call.data == "ask_ai":
        msg = bot.send_message(call.message.chat.id, "💬 Задайте вопрос:")
        bot.register_next_step_handler(msg, ask_ai_handler)


def add_post(message):
    posts = load_posts()
    posts.append({
        "text": message.text,
        "title": message.text[:50],
        "status": "pending"
    })
    save_posts(posts)
    bot.send_message(message.chat.id, "✅ Пост добавлен в контент-план!")


def generate_image_handler(message):
    url = generate_image(message.text)
    bot.send_message(
        message.chat.id,
        f"🎨 Результат:\n{url}"
    )


def ask_ai_handler(message):
    response = generate_text(message.text)
    bot.send_message(
        message.chat.id,
        f"💬 <b>Ответ ИИ:</b>\n\n{response}",
        parse_mode="HTML"
    )


# ==========================
# Сбор лидов (заглушка - используй основной бот)
# ==========================


@bot.message_handler(func=lambda message: True)
def echo(message):
    """Эхо для неизвестных сообщений"""
    if message.chat.type == "private":
        bot.send_message(
            message.chat.id,
            "Используйте меню /start"
        )


# ==========================
# Запуск бота
# ==========================
print("🎯 Content Bot запущен...")
bot.polling(non_stop=True)
