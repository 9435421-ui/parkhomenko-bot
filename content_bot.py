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
# Состояния: awaiting_text, awaiting_photos
posts_in_progress = {}  # user_id: {"photos": [], "step": "waiting_for_text"}
# ==========================

@bot.message_handler(commands=["start"])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📸 Фото + пост", callback_data="photo_post"))
    markup.add(InlineKeyboardButton("📝 Только пост", callback_data="text_post"))
    markup.add(InlineKeyboardButton("📋 Контент-план", callback_data="view_plan"))
    markup.add(InlineKeyboardButton("📊 Статистика", callback_data="stats"))
    
    bot.send_message(
        message.chat.id,
        "🎯 <b>Контент-бот ТЕРИОН</b>\n\n"
        "📸 <b>Фото + пост</b> — загрузить фото и написать текст\n"
        "📝 <b>Только пост</b> — без фото\n\n"
        "Выберите действие:",
        reply_markup=markup,
        parse_mode="HTML"
    )

# ==========================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if call.data == "photo_post":
        # Начинаем процесс: фото + пост
        posts_in_progress[user_id] = {"photos": [], "text": None}
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="cancel"))
        
        bot.send_message(
            call.message.chat.id,
            "📸 <b>Фото + пост</b>\n\n"
            "1️⃣ Отправьте фото объекта\n"
            "2️⃣ Напишите текст поста\n\n"
            "Начните с фото:",
            reply_markup=markup,
            parse_mode="HTML"
        )
        # Переходим к ожиданию фото
        bot.register_next_step_handler(call.message, handle_photo)
        
    elif call.data == "text_post":
        # Только текст поста
        posts_in_progress[user_id] = {"photos": [], "text": None}
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="cancel"))
        
        bot.send_message(
            call.message.chat.id,
            "📝 <b>Только пост</b>\n\n"
            "Напишите текст поста (заголовок + текст):",
            reply_markup=markup,
            parse_mode="HTML"
        )
        # Переходим к ожиданию текста
        bot.register_next_step_handler(call.message, handle_post_text)
        
    elif call.data == "view_plan":
        posts = load_posts()
        if posts:
            text = "📋 <b>Контент-план:</b>\n\n"
            for i, post in enumerate(posts[:10], 1):
                has_photo = "📸" if post.get('image_url') else ""
                text += f"{i}. {has_photo} {post.get('title', 'Без темы')[:35]}\n"
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
        
    elif call.data == "cancel":
        posts_in_progress.pop(user_id, None)
        start(call.message)
        
    elif call.data == "back":
        posts_in_progress.pop(user_id, None)
        start(call.message)

# ==========================
# Обработка фото
# ==========================
def handle_photo(message):
    user_id = message.from_user.id
    
    if message.photo:
        file_id = message.photo[-1].file_id
        if user_id in posts_in_progress:
            posts_in_progress[user_id]["photos"].append(file_id)
        
        count = len(posts_in_progress[user_id]["photos"])
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Добавить текст поста", callback_data="add_text"))
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="cancel"))
        
        bot.send_message(
            message.chat.id,
            f"✅ Фото {count} загружено!\n\n"
            "Напишите текст поста или нажмите 'Добавить текст':",
            reply_markup=markup
        )
        # Переходим к ожиданию текста
        bot.register_next_step_handler(message, handle_post_text)
        
    elif message.text and message.text.lower() in ["◀️", "назад", "отмена", "cancel", "в меню"]:
        posts_in_progress.pop(user_id, None)
        start(message)
    else:
        # Текст вместо фото — сразу переходим к тексту
        handle_post_text(message)

# ==========================
# Обработка текста поста
# ==========================
def handle_post_text(message):
    user_id = message.from_user.id
    
    if not message.text:
        bot.send_message(message.chat.id, "📝 Напишите текст поста:")
        bot.register_next_step_handler(message, handle_post_text)
        return
    
    text = message.text.strip()
    
    # Проверяем - это вопрос или пост?
    question_starters = ["?", "как", "что", "зачем", "почему", "какой", "какие", "какая", "можно", "нужно", "документы", "подскажи"]
    is_question = text.lower().startswith(tuple(question_starters)) or "?" in text
    
    if is_question and len(text) < 200:
        bot.send_message(
            message.chat.id,
            "❌ <b>Это вопрос, а не пост!</b>\n\n"
            "💬 Вопросы консультанту → @Parkhovenko_i_kompaniya_bot\n\n"
            "◀️ В меню",
            parse_mode="HTML"
        )
        posts_in_progress.pop(user_id, None)
        return
    
    if user_id in posts_in_progress:
        posts_in_progress[user_id]["text"] = text
    
    # Сохраняем пост
    photos = posts_in_progress.get(user_id, {}).get("photos", [])
    
    try:
        lines = text.split('\n')
        title = lines[0] if lines else "Пост"
        body = '\n'.join(lines[1:]) if len(lines) > 1 else lines[0]
        
        posts = load_posts()
        post_id = len(posts) + 1
        posts.append({
            "id": post_id,
            "title": title[:100],
            "body": body,
            "text": text,
            "status": "pending",
            "photos": photos,
            "admin_id": user_id
        })
        save_posts(posts)
        
        # Отправляем в группу
        username = message.from_user.username or message.from_user.full_name or "Админ"
        
        if photos:
            # Фото + текст
            text_for_group = f"📸📝 <b>Пост с фото #{post_id}</b>\n\n<b>{title}</b>\n\n{body}\n\n👤 @{username}"
            if len(photos) == 1:
                bot.send_photo(LEADS_GROUP_CHAT_ID, photos[0], caption=text_for_group, message_thread_id=THREAD_ID_DRAFTS, parse_mode="HTML")
            else:
                media = [telebot.types.InputMediaPhoto(p) for p in photos]
                media[0].caption = text_for_group
                bot.send_media_group(LEADS_GROUP_CHAT_ID, media, message_thread_id=THREAD_ID_DRAFTS)
        else:
            # Только текст
            text_for_group = f"📝 <b>Пост #{post_id}</b>\n\n<b>{title}</b>\n\n{body}\n\n👤 @{username}"
            bot.send_message(LEADS_GROUP_CHAT_ID, text_for_group, message_thread_id=THREAD_ID_DRAFTS, parse_mode="HTML")
        
        bot.send_message(
            message.chat.id,
            f"✅ Пост #{post_id} готов!\n\n"
            f"📸 Фото: {len(photos)} шт.\n"
            f"📝 Отправлен в рабочую группу на проверку.",
            parse_mode="HTML"
        )
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")
    
    posts_in_progress.pop(user_id, None)

# ==========================
@bot.message_handler(func=lambda m: True)
def echo(message):
    if message.chat.type == "private":
        posts_in_progress.pop(message.from_user.id, None)
        start(message)

print("🎯 Content Bot запущен...")
bot.polling(non_stop=True)
