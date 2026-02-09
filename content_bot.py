"""
Content Bot v2 — бот для создания AI-контента.
"""
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import json
import os
from datetime import datetime
from dotenv import load_dotenv

# Импортируем агентов
from content_agent import ContentAgent
from agents.viral_hooks_agent import ViralHooksAgent

load_dotenv()

BOT_TOKEN = os.getenv("CONTENT_BOT_TOKEN")
LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "-1003370698977"))
THREAD_ID_DRAFTS = int(os.getenv("THREAD_ID_DRAFTS", "85"))

if not BOT_TOKEN:
    raise RuntimeError("CONTENT_BOT_TOKEN must be set in .env")

bot = telebot.TeleBot(BOT_TOKEN)

# === AGENTS ===
content_agent = ContentAgent()
viral_hooks_agent = ViralHooksAgent()

# === STORAGE ===
POSTS_FILE = "content_posts.json"

def load_posts():
    try:
        with open(POSTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_posts(posts):
    with open(POSTS_FILE, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)

# === USER STATE ===
user_state = {}

# === MAIN MENU ===
@bot.message_handler(commands=["start"])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📸 Фото + ИИ-пост", callback_data="ai_post"))
    markup.add(InlineKeyboardButton("📝 Только текст → ИИ", callback_data="ai_text"))
    markup.add(InlineKeyboardButton("📅 Серия постов", callback_data="ai_series"))
    markup.add(InlineKeyboardButton("📋 Мои посты", callback_data="my_posts"))
    
    bot.send_message(
        message.chat.id,
        "🎯 <b>Content Bot v2</b>\n\n"
        "🤖 <b>AI-агенты делают рутину за вас!</b>\n\n"
        "📸 <b>Фото + ИИ-пост</b> — загрузите фото, ИИ создаст пост\n"
        "📝 <b>Только текст → ИИ</b> — тема, ИИ улучшит\n"
        "📅 <b>Серия постов</b> — тема + дней, ИИ сделает цепочку\n"
        "📋 <b>Мои посты</b> — просмотр и публикация\n\n"
        "Выберите:",
        reply_markup=markup,
        parse_mode="HTML"
    )

# === CALLBACKS ===
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if call.data == "ai_post":
        user_state[user_id] = {"step": "photo", "photos": []}
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        bot.send_message(call.message.chat.id, "📸 <b>Фото + ИИ-пост</b>\n\nЗагрузите фото объекта:", reply_markup=markup, parse_mode="HTML")
        bot.register_next_step_handler(call.message, handle_ai_photo)
        
    elif call.data == "ai_text":
        user_state[user_id] = {"step": "text_topic"}
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        bot.send_message(call.message.chat.id, "📝 <b>Только текст → ИИ</b>\n\nВаша тема:", reply_markup=markup, parse_mode="HTML")
        bot.register_next_step_handler(call.message, handle_ai_text_topic)
        
    elif call.data == "ai_series":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("7 дней", callback_data="series_7"))
        markup.add(InlineKeyboardButton("14 дней", callback_data="series_14"))
        markup.add(InlineKeyboardButton("30 дней", callback_data="series_30"))
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        bot.send_message(call.message.chat.id, "📅 <b>Серия постов</b>\n\nВыберите длительность:", reply_markup=markup, parse_mode="HTML")
        
    elif call.data.startswith("series_"):
        days = int(call.data.split("_")[1])
        user_state[user_id] = {"step": "series_topic", "days": days}
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        bot.send_message(call.message.chat.id, f"📅 <b>Серия на {days} дней</b>\n\nВведите тему:", reply_markup=markup, parse_mode="HTML")
        bot.register_next_step_handler(call.message, handle_series_topic)
        
    elif call.data == "my_posts":
        show_posts(call.message)
        
    elif call.data == "back":
        user_state.pop(user_id, None)
        start(call.message)

# === 📸 AI ФОТО + ПОСТ ===
def handle_ai_photo(message):
    user_id = message.from_user.id
    if message.photo:
        file_id = message.photo[-1].file_id
        if user_id in user_state:
            user_state[user_id]["photos"].append(file_id)
        count = len(user_state[user_id]["photos"])
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Хватит фото", callback_data="photos_done"))
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        bot.send_message(message.chat.id, f"✅ Фото {count}! Теперь тема поста:", reply_markup=markup)
        bot.register_next_step_handler(message, handle_ai_topic)
    else:
        bot.send_message(message.chat.id, "📸 Загрузите фото:")

def handle_ai_topic(message):
    user_id = message.from_user.id
    if user_id in user_state:
        user_state[user_id]["topic"] = message.text
    generate_ai_variants(message)

def generate_ai_variants(message):
    user_id = message.from_user.id
    topic = user_state.get(user_id, {}).get("topic", "перепланировка")
    photos = user_state.get(user_id, {}).get("photos", [])
    
    bot.send_message(message.chat.id, "🎨 ИИ создаёт варианты постов...")
    
    # 3 варианта постов
    variants = [
        {
            "type": "🧠 Экспертный",
            "text": f"<b>{topic}</b>\n\nРазберём по полочкам: что нужно знать.\n\n📋 Ключевые моменты:\n• Пункт 1\n• Пункт 2\n• Пункт 3\n\n💡 Вывод: это профессиональная задача.\n\n👉 Запишитесь: @Parkhovenko_i_kompaniya_bot",
            "hashtags": f"#{topic.replace(' ', '')} #перепланировка #Москва"
        },
        {
            "type": "💭 Эмоциональный",
            "text": f"😱 Знаете ли вы, что {topic.lower()} может...\n\nМы видели много случаев с серьёзными проблемами.\n\nНо есть способ избежать их! ✅\n\nЗапишитесь на консультацию.",
            "hashtags": f"#{topic.replace(' ', '')} #советы"
        },
        {
            "type": "🎯 Продающий",
            "text": f"<b>Хотите решить вопрос с {topic.lower()}?</b>\n\nНаши эксперты:\n✅ Бесплатный аудит\n✅ Подготовка за 3 дня\n✅ Гарантия результата\n\n📞 Записаться: @Parkhovenko_i_kompaniya_bot\n\n💰 Первый осмотр — бесплатно!",
            "hashtags": f"#{topic.replace(' ', '')} #эксперты"
        }
    ]
    
    if user_id in user_state:
        user_state[user_id]["variants"] = variants
    
    # Показываем варианты
    for i, v in enumerate(variants, 1):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton(f"✅ Вариант {i}", callback_data=f"select_variant_{i}"))
        preview = v["text"][:150] + "..."
        bot.send_message(message.chat.id, f"📝 <b>Вариант {i}: {v['type']}</b>\n\n{preview}\n\n{v['hashtags']}", reply_markup=markup, parse_mode="HTML")
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
    bot.send_message(message.chat.id, "Выберите вариант:", reply_markup=markup)

# === 📝 AI ТЕКСТ ===
def handle_ai_text_topic(message):
    user_id = message.from_user.id
    if not message.text:
        bot.send_message(message.chat.id, "📝 Напишите тему:")
        return
    
    topic = message.text
    bot.send_message(message.chat.id, f"🎨 ИИ обрабатывает: {topic}...")
    
    improved_text = f"<b>{topic}</b>\n\nРассказываем экспертный разбор.\n\n🔑 Ключевые моменты:\n• Пункт 1\n• Пункт 2\n• Пункт 3\n\n💡 Обращайтесь к профи — @Parkhovenko_i_kompaniya_bot"
    hashtags = f"#{topic.replace(' ', '')} #перепланировка #Москва"
    
    # Сохраняем
    posts = load_posts()
    post_id = len(posts) + 1
    posts.append({
        "id": post_id, "type": "ai_text", "topic": topic,
        "text": improved_text, "hashtags": hashtags,
        "status": "draft", "date": datetime.now().strftime("%d.%m.%Y"),
        "user_id": user_id
    })
    save_posts(posts)
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📤 В группу", callback_data=f"publish_{post_id}"))
    markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
    bot.send_message(message.chat.id, f"📝 <b>ИИ-пост готов!</b>\n\n{improved_text}\n\n{hashtags}", reply_markup=markup, parse_mode="HTML")

# === 📅 СЕРИЯ ПОСТОВ ===
def handle_series_topic(message):
    user_id = message.from_user.id
    topic = message.text
    days = user_state.get(user_id, {}).get("days", 7)
    
    if not topic:
        bot.send_message(message.chat.id, "📝 Введите тему:")
        return
    
    bot.send_message(message.chat.id, f"🎯 Генерирую серию на {days} дней...")
    
    chain = generate_warmup_chain(topic, days)
    
    posts = load_posts()
    for item in chain:
        post_id = len(posts) + 1
        posts.append({
            "id": post_id, "type": "series", "day": item["day"],
            "topic": item["topic"], "text": item["text"],
            "status": "draft", "date": datetime.now().strftime("%d.%m.%Y"),
            "user_id": user_id
        })
    save_posts(posts)
    
    text = f"📅 <b>Серия на {days} дней готова!</b>\n\n"
    for item in chain[:5]:
        text += f"📌 День {item['day']}: {item['topic']}\n"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📋 Все посты", callback_data="my_posts"))
    markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

def generate_warmup_chain(topic, days):
    """Генерирует цепочку постов"""
    chain = []
    
    themes = [
        ("Боль", f"😱 Опасность: штрафы за {topic.lower()}"),
        ("Эксперт", f"📋 Что можно и нельзя при {topic.lower()}"),
        ("Эксперт", f"📁 Какие документы нужны для {topic.lower()}"),
        ("Эксперт", f"🔄 Как проходит {topic.lower()}"),
        ("Соцдок", f"🏠 Наши кейсы: успешные проекты"),
        ("Соцдок", f"⭐ Отзывы клиентов"),
        ("CTA", f"🎯 Запишитесь на консультацию"),
    ]
    
    for i, (theme, text_template) in enumerate(themes[:days], 1):
        chain.append({
            "day": i,
            "theme": theme,
            "topic": text_template.format(topic=topic),
            "text": f"<b>{text_template.format(topic=topic)}</b>\n\nПодробный экспертный разбор темы.\n\n💡 Подробности у специалистов: @Parkhovenko_i_kompaniya_bot"
        })
    
    return chain

# === 📋 МОИ ПОСТЫ ===
def show_posts(message):
    posts = load_posts()
    
    if not posts:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        bot.send_message(message.chat.id, "📭 Постов пока нет.", reply_markup=markup)
        return
    
    text = "📋 <b>Мои посты</b>\n\n"
    for post in posts[-10:]:
        status = "⏳" if post.get("status") == "draft" else "📤"
        topic = post.get("topic", post.get("text", "Пост")[:25])
        text += f"{status} #{post.get('id', '?')} - {topic}\n"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

# === ECHO ===
@bot.message_handler(func=lambda m: True)
def echo(message):
    if message.chat.type == "private":
        user_state.pop(message.from_user.id, None)
        start(message)

print("🎯 Content Bot v2 запущен...")
bot.polling(non_stop=True)
