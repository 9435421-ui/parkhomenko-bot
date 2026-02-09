"""
Content Bot — бот для контента и загрузки материалов.
"""
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import json
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("CONTENT_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003612599428"))
LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "-1003370698977"))
THREAD_ID_DRAFTS = int(os.getenv("THREAD_ID_DRAFTS", "85"))

if not BOT_TOKEN:
    raise RuntimeError("CONTENT_BOT_TOKEN must be set in .env")

bot = telebot.TeleBot(BOT_TOKEN)

# ==========================
# Файлы
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
# Клавиатуры
# ==========================


def get_main_menu():
    """Главное меню контент-бота"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton("📸 Загрузить фото", callback_data="upload_photo")],
            [InlineKeyboardButton("📝 Готовый пост", callback_data="ready_post")],
            [InlineKeyboardButton("📋 Контент-план", callback_data="view_plan")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        ]
    )


def get_back_menu():
    """Кнопка назад"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton("◀️ В меню", callback_data="back_to_menu")]
        ]
    )


# ==========================
# Меню
# ==========================


@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "🎯 <b>Контент-бот ТЕРИОН</b>\n\n"
        "Выберите действие:",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "upload_photo":
        bot.send_message(
            call.message.chat.id,
            "📸 <b>Загрузка фото объекта</b>\n\n"
            "Отправьте фото объекта недвижимости.\n"
            "Можно отправить 1 фото или альбом (до 10 фото).\n\n"
            "После загрузки бот:\n"
            "1. Проанализирует фото через Яндекс Vision\n"
            "2. Сохранит в базу\n"
            "3. Отправит в рабочую группу на проверку",
            reply_markup=get_back_menu(),
            parse_mode="HTML"
        )
        # Регистрируем следующий шаг для фото
        bot.register_next_step_handler(call.message, handle_photo)
        
    elif call.data == "ready_post":
        msg = bot.send_message(
            call.message.chat.id,
            "📝 <b>Готовый пост</b>\n\n"
            "Отправьте текст поста который хотите опубликовать.\n"
            "Можно добавить:\n"
            "• Заголовок\n"
            "• Текст\n"
            "• Ссылку на фото/изображение",
            reply_markup=get_back_menu(),
            parse_mode="HTML"
        )
        bot.register_next_step_handler(call.message, handle_ready_post)
        
    elif call.data == "view_plan":
        posts = load_posts()
        if posts:
            response = "📋 <b>Контент-план:</b>\n\n"
            for i, post in enumerate(posts[:10], 1):
                title = post.get('title', 'Без темы')[:40]
                status = post.get('status', 'pending')
                response += f"{i}. {title} [{status}]\n"
            bot.send_message(call.message.chat.id, response, reply_markup=get_back_menu(), parse_mode="HTML")
        else:
            bot.send_message(call.message.chat.id, "📭 Контент-план пуст.", reply_markup=get_back_menu())
            
    elif call.data == "stats":
        posts = load_posts()
        published = len([p for p in posts if p.get('status') == 'published'])
        pending = len([p for p in posts if p.get('status') == 'pending'])
        bot.send_message(
            call.message.chat.id,
            f"📊 <b>Статистика:</b>\n\n"
            f"📝 Всего постов: {len(posts)}\n"
            f"✅ Опубликовано: {published}\n"
            f"⏳ В ожидании: {pending}",
            reply_markup=get_back_menu(),
            parse_mode="HTML"
        )
        
    elif call.data == "back_to_menu":
        bot.edit_message_text(
            "🎯 <b>Контент-бот ТЕРИОН</b>\n\n"
            "Выберите действие:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_main_menu(),
            parse_mode="HTML"
        )


# ==========================
# Обработка фото
# ==========================

photos_buffer = {}


def handle_photo(message):
    """Обработка загруженных фото"""
    user_id = message.from_user.id
    
    if message.photo:
        file_id = message.photo[-1].file_id
        if user_id not in photos_buffer:
            photos_buffer[user_id] = []
        photos_buffer[user_id].append(file_id)
        
        count = len(photos_buffer[user_id])
        bot.send_message(
            message.chat.id,
            f"✅ Фото {count} загружено!\n\n"
            "Отправьте ещё фото или нажмите 'Готово' для сохранения.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton("✅ Готово", callback_data=f"save_photos:{user_id}")],
                    [InlineKeyboardButton("◀️ Отмена", callback_data="cancel_photos")]
                ]
            )
        )
        
    elif message.text and message.text.lower() in ["готово", "done", "ok"]:
        if user_id in photos_buffer and photos_buffer[user_id]:
            save_photos_to_group(message, user_id)
        else:
            bot.send_message(message.chat.id, "📭 Нет фото для сохранения.", reply_markup=get_main_menu())
            
    elif message.text and message.text.lower() in ["отмена", "cancel"]:
        photos_buffer.pop(user_id, None)
        bot.send_message(message.chat.id, "❌ Отменено.", reply_markup=get_main_menu())
        
    else:
        bot.send_message(message.chat.id, "📸 Отправьте фото или нажмите 'Готово'")


def save_photos_to_group(message, user_id):
    """Сохраняет фото и отправляет в группу"""
    photos = photos_buffer[user_id]
    
    # Формируем сообщение
    username = message.from_user.username or message.from_user.full_name or "Админ"
    text = (
        f"📸 <b>Новые фото объекта</b>\n\n"
        f"👤 Загрузил: @{username}\n"
        f"📁 Фото: {len(photos)} шт.\n\n"
        f"<i>Для добавления описания и публикации используйте админ-панель.</i>"
    )
    
    try:
        # Отправляем фото в группу
        if len(photos) == 1:
            bot.send_photo(
                chat_id=LEADS_GROUP_CHAT_ID,
                photo=photos[0],
                caption=text,
                message_thread_id=THREAD_ID_DRAFTS,
                parse_mode="HTML"
            )
        else:
            # Альбом
            media = [telebot.types.InputMediaPhoto(photo) for photo in photos]
            media[0].caption = text
            media[0].parse_mode = "HTML"
            bot.send_media_group(
                chat_id=LEADS_GROUP_CHAT_ID,
                media=media,
                message_thread_id=THREAD_ID_DRAFTS
            )
        
        # Ответ пользователю
        bot.send_message(
            message.chat.id,
            f"✅ {len(photos)} фото отправлено в рабочую группу!",
            reply_markup=get_main_menu()
        )
        
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка отправки: {e}",
            reply_markup=get_main_menu()
        )
    
    # Очищаем буфер
    photos_buffer.pop(user_id, None)


# ==========================
# Обработка готового поста
# ==========================

def handle_ready_post(message):
    """Обработка готового поста"""
    try:
        # Парсим текст
        lines = message.text.split('\n')
        title = lines[0] if lines else "Пост"
        body = '\n'.join(lines[1:]) if len(lines) > 1 else lines[0]
        
        # Сохраняем в план
        posts = load_posts()
        posts.append({
            "title": title[:100],
            "body": body,
            "status": "pending",
            "image_url": None,
            "admin_id": message.from_user.id
        })
        save_posts(posts)
        
        # Отправляем в группу
        text = (
            f"📝 <b>Готовый пост</b>\n\n"
            f"<b>{title}</b>\n\n"
            f"{body}\n\n"
            f"👤 @{message.from_user.username or 'admin'}"
        )
        
        bot.send_message(
            chat_id=LEADS_GROUP_CHAT_ID,
            text=text,
            message_thread_id=THREAD_ID_DRAFTS,
            parse_mode="HTML"
        )
        
        bot.send_message(
            message.chat.id,
            "✅ Пост добавлен в план и отправлен в группу!",
            reply_markup=get_main_menu()
        )
        
    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка: {e}",
            reply_markup=get_main_menu()
        )


# ==========================
# Эхо
# ==========================

@bot.message_handler(func=lambda message: True)
def echo(message):
    if message.chat.type == "private":
        bot.send_message(
            message.chat.id,
            "🎯 Используйте меню /start",
            reply_markup=get_main_menu()
        )


# ==========================
# Запуск
# ==========================
print("🎯 Content Bot запущен...")
bot.polling(non_stop=True)
