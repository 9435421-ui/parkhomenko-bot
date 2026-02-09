"""
Content Bot - бот для создания и планирования контента.
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

if not BOT_TOKEN:
    raise RuntimeError("CONTENT_BOT_TOKEN must be set in .env")

bot = telebot.TeleBot(BOT_TOKEN)

# === POSTS STORAGE ===
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
    markup.add(InlineKeyboardButton("📸 Фото + пост", callback_data="photo_post"))
    markup.add(InlineKeyboardButton("📅 7 дней прогрева", callback_data="warmup_7"))
    markup.add(InlineKeyboardButton("🎨 ИИ-Визуал", callback_data="ai_image"))
    markup.add(InlineKeyboardButton("📋 Интерактивный План", callback_data="view_plan"))
    
    bot.send_message(
        message.chat.id,
        "🎯 <b>Content Bot</b>\n\n"
        "📸 <b>Фото + пост</b> - загрузить фото и создать пост\n"
        "📅 <b>7 дней прогрева</b> - воронка продаж\n"
        "🎨 <b>ИИ-Визуал</b> - генерация изображений\n"
        "📋 <b>Интерактивный План</b> - управление постами\n\n"
        "Выберите действие:",
        reply_markup=markup,
        parse_mode="HTML"
    )

# === CALLBACK HANDLER ===
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if call.data == "photo_post":
        # ЭТАП 2: Фото + пост
        user_state[user_id] = {"photos": [], "step": "waiting_photo"}
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        bot.send_message(
            call.message.chat.id,
            "📸 <b>Фото + пост</b>\n\n"
            "1️⃣ Загрузите фото объекта\n"
            "2️⃣ Напишите текст поста\n"
            "3️⃣ Пост отправится в рабочую группу\n\n"
            "Загрузите фото:",
            reply_markup=markup,
            parse_mode="HTML"
        )
        bot.register_next_step_handler(call.message, handle_photo)
        
    elif call.data == "warmup_7":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🔄 Сгенерировать", callback_data="do_warmup"))
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        bot.send_message(
            call.message.chat.id,
            "📅 <b>7 дней прогрева</b>\n\n"
            "🤖 ИИ создаст воронку:\n"
            "• День 1: Боль клиента\n"
            "• День 2-4: Экспертный контент\n"
            "• День 5-6: Социальное доказательство\n"
            "• День 7: CTA\n\n"
            "Начать?",
            reply_markup=markup,
            parse_mode="HTML"
        )
        
    elif call.data == "do_warmup":
        generate_warmup(call.message)
        
    elif call.data == "ai_image":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        bot.send_message(
            call.message.chat.id,
            "🎨 <b>ИИ-Визуал</b>\n\n"
            "Опишите что нужно изобразить:\n"
            "• Интерьер\n"
            "• Схема\n"
            "• Чертеж\n\n"
            "Без текста на картинке!",
            reply_markup=markup,
            parse_mode="HTML"
        )
        bot.register_next_step_handler(call.message, handle_ai_image)
        
    elif call.data == "view_plan":
        show_plan(call.message)
        
    elif call.data == "back":
        user_state.pop(user_id, None)
        start(call.message)

# === ЭТАП 2: ФОТО + ПОСТ ===
def handle_photo(message):
    """Обработка загрузки фото"""
    user_id = message.from_user.id
    
    if message.photo:
        file_id = message.photo[-1].file_id
        if user_id in user_state:
            user_state[user_id]["photos"].append(file_id)
        
        count = len(user_state[user_id]["photos"])
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ Это все фото", callback_data="photos_done"))
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        
        bot.send_message(
            message.chat.id,
            f"✅ Фото {count} загружено!\n\n"
            "Теперь напишите текст поста:",
            reply_markup=markup
        )
        bot.register_next_step_handler(message, handle_post_text)
        
    else:
        bot.send_message(message.chat.id, "📸 Загрузите фото или нажмите 'В меню':")

def handle_post_text(message):
    """Обработка текста поста"""
    user_id = message.from_user.id
    
    if not message.text:
        bot.send_message(message.chat.id, "📝 Напишите текст поста:")
        bot.register_next_step_handler(message, handle_post_text)
        return
    
    if user_id in user_state:
        user_state[user_id]["text"] = message.text
    
    # Сохраняем пост
    save_post_to_group(message)

def save_post_to_group(message):
    """Сохраняет пост и отправляет в рабочую группу"""
    user_id = message.from_user.id
    data = user_state.get(user_id, {})
    
    photos = data.get("photos", [])
    text = data.get("text", message.text if message.text else "")
    
    if not text:
        bot.send_message(message.chat.id, "📝 Текст поста обязателен!")
        return
    
    # Формируем пост
    posts = load_posts()
    post_id = len(posts) + 1
    today = datetime.now().strftime("%d.%m.%Y")
    
    post = {
        "id": post_id,
        "text": text,
        "photos": photos,
        "status": "draft",
        "date": today,
        "user_id": user_id,
        "username": message.from_user.username
    }
    posts.append(post)
    save_posts(posts)
    
    # Отправляем в рабочую группу
    username = message.from_user.username or "Админ"
    
    preview = text[:150] + "..." if len(text) > 150 else text
    text_group = f"📝 <b>Пост #{post_id}</b>\n\n{preview}\n\n👤 @{username}"
    
    try:
        if photos:
            if len(photos) == 1:
                bot.send_photo(
                    LEADS_GROUP_CHAT_ID,
                    photos[0],
                    caption=text_group,
                    message_thread_id=THREAD_ID_DRAFTS,
                    parse_mode="HTML"
                )
            else:
                media = [InputMediaPhoto(p) for p in photos]
                media[0].caption = text_group
                bot.send_media_group(
                    LEADS_GROUP_CHAT_ID,
                    media,
                    message_thread_id=THREAD_ID_DRAFTS
                )
        else:
            bot.send_message(
                LEADS_GROUP_CHAT_ID,
                text_group,
                message_thread_id=THREAD_ID_DRAFTS,
                parse_mode="HTML"
            )
        
        # Ответ пользователю
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📋 Интерактивный План", callback_data="view_plan"))
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        
        bot.send_message(
            message.chat.id,
            f"✅ <b>Пост #{post_id} создан!</b>\n\n"
            f"📸 Фото: {len(photos)} шт.\n"
            f"📤 Отправлен в рабочую группу\n\n"
            f"🆔 THREAD_ID_DRAFTS = {THREAD_ID_DRAFTS}",
            reply_markup=markup,
            parse_mode="HTML"
        )
        
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка отправки: {e}\n\n"
            f"Пост сохранён локально (ID: {post_id})"
        )
    
    # Очищаем состояние
    user_state.pop(user_id, None)

# === 7 ДНЕЙ ПРОГРЕВА ===
def generate_warmup(message):
    """Генерирует цепочку 7 дней"""
    bot.send_message(message.chat.id, "🎯 Генерирую цепочку '7 дней прогрева'...")
    
    warmup_chain = [
        {"day": 1, "theme": "Боль", "topic": "Штрафы", "text": "😱 За незаконную перепланировку: штраф до 5000 ₽, предписание вернуть квартиру в исходное состояние, запрет на продажу."},
        {"day": 2, "theme": "Эксперт", "topic": "Что можно", "text": "📋 Что МОЖНО: санузлы, перегородки, перенос кухни. Что НЕЛЬЗЯ: несущие стены, вентиляция, балконы."},
        {"day": 3, "theme": "Эксперт", "topic": "Документы", "text": "📁 Документы: паспорт БТИ, проект, заявление. Без них согласование невозможно."},
        {"day": 4, "theme": "Эксперт", "topic": "Процесс", "text": "🔄 Этапы: аудит → проект → согласование → работы → приёмка. Весь процесс 2-4 месяца."},
        {"day": 5, "theme": "Соцдок", "topic": "Кейсы", "text": "🏠 Сделали перепланировку для 150+ клиентов. Средний срок - 2.5 месяца. Все довольны!"},
        {"day": 6, "theme": "Соцдок", "topic": "Отзывы", "text": "⭐ 'Спасли от штрафа!', 'Всё сделали быстро', 'Профессионалы' - отзывы наших клиентов."},
        {"day": 7, "theme": "CTA", "topic": "Запись", "text": "🎯 Запишитесь на бесплатную консультацию: @Parkhovenko_i_kompaniya_bot\n\nПервый осмотр - бесплатно!"}
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
    markup.add(InlineKeyboardButton("📋 Интерактивный План", callback_data="view_plan"))
    markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

# === ИИ-ВИЗУАЛ ===
def handle_ai_image(message):
    """Генерация изображений"""
    if message.text:
        bot.send_message(
            message.chat.id,
            f"🎨 Генерирую изображение: {message.text}\n\n"
            f"⚠️ ИИ-Визуал временно недоступен (идёт настройка API)"
        )

# === ИНТЕРАКТИВНЫЙ ПЛАН ===
def show_plan(message):
    """Показывает список постов"""
    posts = load_posts()
    
    if not posts:
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
        bot.send_message(message.chat.id, "📭 Постов пока нет.", reply_markup=markup)
        return
    
    text = "📋 <b>Контент-План</b>\n\n"
    for post in posts[-10:]:
        status = "⏳" if post.get("status") == "draft" else "📤"
        topic = post.get("topic", post.get("text", "Пост")[:30])
        text += f"{status} #{post.get('id', '?')} - {topic}\n"
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📄 Все посты", callback_data="all_posts"))
    markup.add(InlineKeyboardButton("◀️ В меню", callback_data="back"))
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode="HTML")

# === ECHO ===
@bot.message_handler(func=lambda m: True)
def echo(message):
    if message.chat.type == "private":
        user_state.pop(message.from_user.id, None)
        start(message)

print("🎯 Content Bot запущен...")
bot.polling(non_stop=True)
