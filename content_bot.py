"""
Content Bot — бот для контента и загрузки материалов.
"""
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import json
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("CONTENT_BOT_TOKEN")
LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "-1003370698977"))
THREAD_ID_DRAFTS = int(os.getenv("THREAD_ID_DRAFTS", "85"))

if not BOT_TOKEN:
    raise RuntimeError("CONTENT_BOT_TOKEN must be set in .env")

bot = telebot.TeleBot(BOT_TOKEN)

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
# Главное меню
# ==========================
@bot.message_handler(commands=["start"])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📸 Загрузить фото", callback_data="upload_photo"))
    markup.add(InlineKeyboardButton("📝 Готовый пост", callback_data="ready_post"))
    markup.add(InlineKeyboardButton("📋 Контент-план", callback_data="view_plan"))
    markup.add(InlineKeyboardButton("📊 Статистика", callback_data="stats"))
    
    bot.send_message(
        message.chat.id,
        "🎯 <b>Контент-бот ТЕРИОН</b>\n\nВыберите действие:",
        reply_markup=markup,
        parse_mode="HTML"
    )

# ==========================
# Callback обработка
# ==========================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "upload_photo":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        
        bot.send_message(
            call.message.chat.id,
            "📸 <b>Загрузка фото объекта</b>\n\n"
            "Отправьте фото объекта недвижимости.\n"
            "После загрузки нажмите 'Готово'.",
            reply_markup=markup,
            parse_mode="HTML"
        )
        bot.register_next_step_handler(call.message, handle_photo)
        
    elif call.data == "ready_post":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        
        bot.send_message(
            call.message.chat.id,
            "📝 <b>Готовый пост</b>\n\n"
            "Отправьте текст поста (заголовок + текст).",
            reply_markup=markup,
            parse_mode="HTML"
        )
        bot.register_next_step_handler(call.message, handle_ready_post)
        
    elif call.data == "view_plan":
        posts = load_posts()
        if posts:
            text = "📋 <b>Контент-план:</b>\n\n"
            for i, post in enumerate(posts[:10], 1):
                text += f"{i}. {post.get('title', 'Без темы')[:40]} [{post.get('status', 'pending')}]\n"
        else:
            text = "📭 Контент-план пуст."
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="HTML")
            
    elif call.data == "stats":
        posts = load_posts()
        published = len([p for p in posts if p.get('status') == 'published'])
        pending = len([p for p in posts if p.get('status') == 'pending'])
        
        text = f"📊 <b>Статистика:</b>\n\n📝 Всего: {len(posts)}\n✅ Опубликовано: {published}\n⏳ Ожидание: {pending}"
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        bot.send_message(call.message.chat.id, text, reply_markup=markup, parse_mode="HTML")
        
    elif call.data == "back":
        start(call.message)

# ==========================
# Обработка фото
# ==========================
photos_buffer = {}

def handle_photo(message):
    user_id = message.from_user.id
    
    if message.photo:
        file_id = message.photo[-1].file_id
        if user_id not in photos_buffer:
            photos_buffer[user_id] = []
        photos_buffer[user_id].append(file_id)
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Готово", callback_data=f"save:{user_id}"))
        markup.add(InlineKeyboardButton("◀️ Отмена", callback_data="cancel"))
        
        bot.send_message(
            message.chat.id,
            f"✅ Фото {len(photos_buffer[user_id])} загружено!",
            reply_markup=markup
        )
        
    elif message.text and message.text.lower() in ["готово", "done"]:
        if user_id in photos_buffer and photos_buffer[user_id]:
            save_photos(message, user_id)
        else:
            bot.send_message(message.chat.id, "📭 Нет фото.")
            
    elif message.text and message.text.lower() in ["отмена", "cancel"]:
        photos_buffer.pop(user_id, None)
        start(message)
    else:
        bot.send_message(message.chat.id, "📸 Отправьте фото или 'Готово'")

def save_photos(message, user_id):
    photos = photos_buffer[user_id]
    username = message.from_user.username or message.from_user.full_name or "Админ"
    
    text = f"📸 <b>Новые фото объекта</b>\n\n👤 @{username}\n📁 {len(photos)} шт."
    
    try:
        if len(photos) == 1:
            bot.send_photo(LEADS_GROUP_CHAT_ID, photos[0], caption=text, message_thread_id=THREAD_ID_DRAFTS, parse_mode="HTML")
        else:
            media = [telebot.types.InputMediaPhoto(p) for p in photos]
            media[0].caption = text
            bot.send_media_group(LEADS_GROUP_CHAT_ID, media, message_thread_id=THREAD_ID_DRAFTS)
        
        bot.send_message(message.chat.id, f"✅ {len(photos)} фото отправлено в группу!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")
    
    photos_buffer.pop(user_id, None)

# ==========================
# Обработка постов
# ==========================
def handle_ready_post(message):
    try:
        lines = message.text.split('\n')
        title = lines[0] if lines else "Пост"
        body = '\n'.join(lines[1:]) if len(lines) > 1 else lines[0]
        
        posts = load_posts()
        posts.append({
            "title": title[:100],
            "body": body,
            "status": "pending",
            "admin_id": message.from_user.id
        })
        save_posts(posts)
        
        text = f"📝 <b>Готовый пост</b>\n\n<b>{title}</b>\n\n{body}\n\n👤 @{message.from_user.username or 'admin'}"
        bot.send_message(LEADS_GROUP_CHAT_ID, text, message_thread_id=THREAD_ID_DRAFTS, parse_mode="HTML")
        
        bot.send_message(message.chat.id, "✅ Пост добавлен в план!")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.message_handler(func=lambda m: True)
def echo(message):
    if message.chat.type == "private":
        start(message)

print("🎯 Content Bot запущен...")
bot.polling(non_stop=True)
