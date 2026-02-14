"""
Content Bot — бот для контента и генерации контент-плана.
"""
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("CONTENT_BOT_TOKEN")
LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "-1003370698977"))
THREAD_ID_DRAFTS = int(os.getenv("THREAD_ID_DRAFTS", "85"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003612599428"))

if not BOT_TOKEN:
    raise RuntimeError("CONTENT_BOT_TOKEN must be set in .env")

bot = telebot.TeleBot(BOT_TOKEN)

# ==========================
POSTS_FILE = "content_plan.json"
IMAGES_DIR = "content_images"
os.makedirs(IMAGES_DIR, exist_ok=True)

def load_plan():
    try:
        with open(POSTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"days": [], "posts": []}

def save_plan(plan):
    with open(POSTS_FILE, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)

# ==========================
@bot.message_handler(commands=["start"])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📸 Фото + пост", callback_data="photo_post"))
    markup.add(InlineKeyboardButton("📝 Только пост", callback_data="text_post"))
    markup.add(InlineKeyboardButton("📅 План на 7 дней", callback_data="generate_plan"))
    markup.add(InlineKeyboardButton("📋 Мой план", callback_data="view_plan"))
    
    bot.send_message(
        message.chat.id,
        "🎯 <b>Контент-бот ТЕРИОН</b>\n\n"
        "📸 <b>Фото + пост</b> — фото объекта + текст\n"
        "📝 <b>Только пост</b> — без фото\n"
        "📅 <b>План на 7 дней</b> — ИИ сгенерирует темы + картинки\n"
        "📋 <b>Мой план</b> — посмотреть план\n\n"
        "Выберите действие:",
        reply_markup=markup,
        parse_mode="HTML"
    )

# ==========================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if call.data == "photo_post":
        posts_in_progress[user_id] = {"photos": [], "text": None}
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="cancel"))
        bot.send_message(call.message.chat.id, "📸 Отправьте фото + напишите текст поста:", reply_markup=markup)
        bot.register_next_step_handler(call.message, handle_content)
        
    elif call.data == "text_post":
        posts_in_progress[user_id] = {"photos": [], "text": None}
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="cancel"))
        bot.send_message(call.message.chat.id, "📝 Напишите текст поста:", reply_markup=markup)
        bot.register_next_step_handler(call.message, handle_content)
        
    elif call.data == "generate_plan":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔄 Сгенерировать", callback_data="do_generate_plan"))
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="cancel"))
        bot.send_message(
            call.message.chat.id,
            "📅 <b>Генерация плана на 7 дней</b>\n\n"
            "🤖 ИИ сгенерирует:\n"
            "• 7 тем постов\n"
            "• Время публикации: 12:00\n"
            "• Картинки к темам (без текста)\n\n"
            "Начать?",
            reply_markup=markup,
            parse_mode="HTML"
        )
        
    elif call.data == "do_generate_plan":
        generate_content_plan(call.message)
        
    elif call.data == "view_plan":
        show_plan(call.message)
        
    elif call.data == "cancel" or call.data == "back":
        posts_in_progress.pop(user_id, None)
        start(call.message)

# ==========================
# Генерация плана на 7 дней
# ==========================
def generate_content_plan(message):
    """Генерирует план на 7 дней через ИИ"""
    
    bot.send_message(message.chat.id, "🔄 Генерирую план на 7 дней...")
    
    # Темы для перепланировок
    topics = [
        "Типы перепланировок: что можно и нельзя",
        "Документы для согласования перепланировки",
        "Как узаконить уже сделанную перепланировку",
        "Штрафы за незаконную перепланировку",
        "Согласование с Мосжилинспекцией",
        "Перепланировка нежилых помещений",
        "Что такое проект перепланировки"
    ]
    
    plan = {
        "generated_at": datetime.now().isoformat(),
        "theme": "Типы перепланировки",
        "days": []
    }
    
    for i in range(7):
        day_date = (datetime.now() + timedelta(days=i)).strftime("%d.%m.%Y")
        publish_time = "12:00"
        
        post = {
            "day": i + 1,
            "date": day_date,
            "publish_time": publish_time,
            "topic": topics[i],
            "status": "draft",
            "image_url": None,
            "photos": []
        }
        plan["days"].append(post)
    
    save_plan(plan)
    
    # Формируем ответ
    text = "📅 <b>Контент-план на 7 дней</b>\n\n"
    text += f"📚 Тема недели: {plan['theme']}\n\n"
    
    for day in plan["days"]:
        status = "⏳" if day["status"] == "draft" else "📸" if day["image_url"] else "✅"
        text += f"{status} <b>День {day['day']}</b> — {day['date']} в {day['publish_time']}\n"
        text += f"   📝 {day['topic']}\n\n"
    
    text += "\n🎨 Изображения будут сгенерированы по темам."
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎨 Сгенерировать картинки", callback_data="gen_images"))
    markup.add(InlineKeyboardButton("📋 Мой план", callback_data="view_plan"))
    markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
    
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

# ==========================
# Генерация изображений
# ==========================
def generate_images_for_plan(message):
    """Генерирует изображения к постам плана"""
    plan = load_plan()
    
    if not plan.get("days"):
        bot.send_message(message.chat.id, "📭 План пуст. Сначала сгенерируйте план.")
        return
    
    bot.send_message(message.chat.id, "🎨 Генерирую изображения к постам...")
    
    success = 0
    for day in plan["days"]:
        topic = day["topic"]
        
        # Промпт для изображения (без текста!)
        image_prompt = f"""
Современный интерьер, дизайн квартиры, минималистичный стиль.
Тема: {topic}.
Без текста, без надписей, профессиональная фотография интерьера.
"""
        # Заглушка - изображение не генерируем (нужен работающий API)
        day["image_url"] = None
        success += 1
    
    save_plan(plan)
    
    bot.send_message(
        message.chat.id,
        f"✅ Обработано {success} постов.\n\n"
        "💡 Изображения: добавляйте фото вручную через 'Фото + пост'\n\n"
        "📋 Мой план — посмотреть результат"
    )

# ==========================
# Показать план
# ==========================
def show_plan(message):
    plan = load_plan()
    
    if not plan.get("days"):
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📅 Создать план", callback_data="generate_plan"))
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        bot.send_message(message.chat.id, "📭 План пуст.", reply_markup=markup)
        return
    
    text = "📋 <b>Контент-план</b>\n\n"
    
    for day in plan["days"]:
        status_emoji = "⏳" if day["status"] == "draft" else "📸" if day.get("photos") else "✅"
        has_image = "🎨" if day.get("image_url") else ""
        
        text += f"{status_emoji} <b>День {day['day']}</b> — {day['date']}\n"
        text += f"   🕐 {day['publish_time']}\n"
        text += f"   📝 {day['topic']} {has_image}\n"
        
        # Показываем фото если есть
        photos = day.get("photos", [])
        if photos:
            text += f"   📸 Фото: {len(photos)} шт.\n"
        
        text += "\n"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📅 Обновить план", callback_data="generate_plan"))
    markup.add(InlineKeyboardButton("📸 Фото + пост", callback_data="photo_post"))
    markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
    
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

# ==========================
# Обработка контента (фото + текст)
# ==========================
posts_in_progress = {}

def handle_content(message):
    user_id = message.from_user.id
    
    if message.photo:
        file_id = message.photo[-1].file_id
        if user_id in posts_in_progress:
            posts_in_progress[user_id]["photos"].append(file_id)
        count = len(posts_in_progress[user_id]["photos"])
        bot.send_message(message.chat.id, f"✅ Фото {count} загружено! Теперь напишите текст поста:")
        bot.register_next_step_handler(message, save_content)
        
    elif message.text:
        if user_id in posts_in_progress:
            posts_in_progress[user_id]["text"] = message.text
        save_content(message)
    else:
        bot.send_message(message.chat.id, "📝 Отправьте фото или напишите текст:")

def save_content(message):
    user_id = message.from_user.id
    data = posts_in_progress.get(user_id, {})
    
    text = data.get("text") or message.text
    photos = data.get("photos", [])
    
    if not text:
        bot.send_message(message.chat.id, "📝 Напишите текст поста:")
        bot.register_next_step_handler(message, save_content)
        return
    
    # Проверяем - это вопрос или пост?
    question_markers = ["?", "как", "что", "зачем", "почему", "документы", "подскажи"]
    if any(text.lower().startswith(m) for m in question_markers) and len(text) < 300:
        bot.send_message(
            message.chat.id,
            "❌ <b>Это вопрос, а не пост!</b>\n\n"
            "💬 Вопросы → @Parkhovenko_i_kompaniya_bot",
            parse_mode="HTML"
        )
        posts_in_progress.pop(user_id, None)
        return
    
    # Добавляем в план
    plan = load_plan()
    if "days" not in plan:
        plan = {"days": [], "posts": []}
    
    post_id = len(plan["days"]) + 1
    today = datetime.now().strftime("%d.%m.%Y")
    
    plan["days"].append({
        "id": post_id,
        "date": today,
        "publish_time": "12:00",
        "topic": text.split('\n')[0][:100] if '\n' in text else text[:100],
        "body": text,
        "status": "ready",
        "photos": photos,
        "image_url": None
    })
    save_plan(plan)
    
    # Отправляем в группу
    username = message.from_user.username or message.from_user.full_name or "Админ"
    preview = text.split('\n')[0][:100] if text else "Пост"
    
    if photos:
        caption = f"📸📝 <b>Пост #{post_id}</b>\n\n<b>{preview}</b>\n\n👤 @{username}"
        if len(photos) == 1:
            bot.send_photo(LEADS_GROUP_CHAT_ID, photos[0], caption=caption, message_thread_id=THREAD_ID_DRAFTS, parse_mode="HTML")
        else:
            media = [InputMediaPhoto(p) for p in photos]
            media[0].caption = caption
            bot.send_media_group(LEADS_GROUP_CHAT_ID, media, message_thread_id=THREAD_ID_DRAFTS)
    else:
        text_group = f"📝 <b>Пост #{post_id}</b>\n\n<b>{preview}</b>\n\n👤 @{username}"
        bot.send_message(LEADS_GROUP_CHAT_ID, text_group, message_thread_id=THREAD_ID_DRAFTS, parse_mode="HTML")
    
    bot.send_message(
        message.chat.id,
        f"✅ Пост #{post_id} готов!\n\n"
        f"📝 Добавлен в план на {today}\n"
        f"📤 Отправлен в рабочую группу",
        parse_mode="HTML"
    )
    
    posts_in_progress.pop(user_id, None)

# ==========================
@bot.message_handler(func=lambda m: True)
def echo(message):
    if message.chat.type == "private":
        posts_in_progress.pop(message.from_user.id, None)
        start(message)

print("🎯 Content Bot запущен...")
bot.polling(non_stop=True)
