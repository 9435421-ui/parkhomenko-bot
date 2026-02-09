"""
Content Bot v2 - креативный бот для контента.
"""
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("CONTENT_BOT_TOKEN")
LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "-1003370698977"))
THREAD_ID_DRAFTS = int(os.getenv("THREAD_ID_DRAFTS", "85"))
THREAD_ID_SEASONAL = int(os.getenv("THREAD_ID_SEASONAL", "87"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003612599428"))

if not BOT_TOKEN:
    raise RuntimeError("CONTENT_BOT_TOKEN must be set in .env")

bot = telebot.TeleBot(BOT_TOKEN)
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

user_state = {}

@bot.message_handler(commands=["start"])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📸 Фото + Умный пост", callback_data="smart_post"))
    markup.add(InlineKeyboardButton("📅 7 дней прогрева", callback_data="warmup_7"))
    markup.add(InlineKeyboardButton("🎨 ИИ-Визуал", callback_data="ai_image"))
    markup.add(InlineKeyboardButton("📋 Интерактивный План", callback_data="interactive_plan"))
    
    bot.send_message(
        message.chat.id,
        "🎯 <b>Content Bot v2</b>\n\n"
        "📸 <b>Фото + Умный пост</b> - 3 варианта (Экспертный/Эмоциональный/Продающий)\n"
        "📅 <b>7 дней прогрева</b> - воронка продаж\n"
        "🎨 <b>ИИ-Визуал</b> - картинки без фото\n"
        "📋 <b>Интерактивный План</b> - управление постами\n\n"
        "Выберите:",
        reply_markup=markup,
        parse_mode="HTML"
    )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if call.data == "smart_post":
        user_state[user_id] = {"step": "waiting_photo", "photos": [], "variants": []}
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        bot.send_message(call.message.chat.id, "📸 <b>Фото + Умный пост</b>\n\nЗагрузите фото объекта:", reply_markup=markup, parse_mode="HTML")
        bot.register_next_step_handler(call.message, handle_smart_photo)
        
    elif call.data == "warmup_7":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔄 Сгенерировать", callback_data="do_warmup"))
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        bot.send_message(call.message.chat.id, "📅 <b>7 дней прогрева</b>\n\nДень 1: Боль\nДень 2-4: Эксперт\nДень 5-6: Соцдок\nДень 7: CTA\n\nНачать?", reply_markup=markup, parse_mode="HTML")
        
    elif call.data == "do_warmup":
        generate_warmup(call.message)
        
    elif call.data == "ai_image":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        bot.send_message(call.message.chat.id, "🎨 <b>ИИ-Визуал</b>\n\nОпишите что изобразить (интерьер, чертеж, схема). Без текста на картинке.", reply_markup=markup, parse_mode="HTML")
        bot.register_next_step_handler(call.message, handle_ai_image)
        
    elif call.data == "interactive_plan":
        show_interactive_plan(call.message)
        
    elif call.data == "back":
        user_state.pop(user_id, None)
        start(call.message)

def handle_smart_photo(message):
    user_id = message.from_user.id
    if message.photo:
        file_id = message.photo[-1].file_id
        if user_id in user_state:
            user_state[user_id]["photos"].append(file_id)
        count = len(user_state[user_id]["photos"])
        bot.send_message(message.chat.id, f"✅ Фото {count}! Теперь напишите тему поста:")
    else:
        bot.send_message(message.chat.id, "📸 Загрузите фото:")

def handle_ai_image(message):
    if message.text:
        bot.send_message(message.chat.id, f"🎨 Генерирую изображение по теме: {message.text}\n\n(ИИ-Визуал временно недоступен - идёт настройка API)")

def generate_warmup(message):
    bot.send_message(message.chat.id, "🎯 Генерирую цепочку '7 дней прогрева'...")
    
    warmup_chain = [
        {"day": 1, "theme": "Боль", "topic": "Штрафы за перепланировку", "text": "😱 За незаконную перепланировку: штраф до 5000 ₽, предписание вернуть квартиру в исходное состояние, запрет на продажу."},
        {"day": 2, "theme": "Эксперт", "topic": "Что можно и нельзя", "text": "📋 Что МОЖНО: санузлы, перегородки, перенос кухни. Что НЕЛЬЗЯ: несущие стены, вентиляция, балконы."},
        {"day": 3, "theme": "Эксперт", "topic": "Документы", "text": "📁 Документы: паспорт БТИ, проект, заявление. Без них согласование невозможно."},
        {"day": 4, "theme": "Эксперт", "topic": "Процесс", "text": "🔄 Этапы: аудит → проект → согласование → работы → приёмка. Весь процесс 2-4 месяца."},
        {"day": 5, "theme": "Соцдок", "topic": "Кейсы", "text": "🏠 Сделали перепланировку для 150+ клиентов. Средний срок - 2.5 месяца. Все довольны!"},
        {"day": 6, "theme": "Соцдок", "topic": "Отзывы", "text": "⭐ 'Спасли от штрафа!','Всё сделали быстро','Профессионалы' - отзывы наших клиентов."},
        {"day": 7, "theme": "CTA", "topic": "Запись на консультацию", "text": "🎯 Запишитесь на бесплатную консультацию: @Parkhovenko_i_kompaniya_bot\n\nПервый осмотр - бесплатно!"}
    ]
    
    posts = load_posts()
    for item in warmup_chain:
        post_id = len(posts) + 1
        posts.append({
            "id": post_id,
            "type": "warmup",
            "day": item["day"],
            "topic": item["topic"],
            "text": item["text"],
            "status": "draft",
            "created_at": datetime.now().isoformat()
        })
    save_posts(posts)
    
    text = "📅 <b>Цепочка '7 дней прогрева' создана!</b>\n\n"
    for item in warmup_chain:
        text += f"📌 День {item['day']}: {item['topic']}\n"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📋 Интерактивный План", callback_data="interactive_plan"))
    markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

def show_interactive_plan(message):
    posts = load_posts()
    if not posts:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        bot.send_message(message.chat.id, "📭 Постов нет.", reply_markup=markup)
        return
    
    text = "📋 <b>Интерактивный План</b>\n\n"
    for post in posts[-10:]:
        status = "⏳" if post.get("status") == "draft" else "📤"
        text += f"{status} #{post.get('id', '?')} - {post.get('topic', 'Без темы')[:30]}\n"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

print("🎯 Content Bot v2 запущен...")
bot.polling(non_stop=True)
