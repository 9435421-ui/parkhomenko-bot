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
CHANNEL_ID_STR = os.getenv("CHANNEL_ID", "")
# Поддержка как числового ID, так и строки с @
if CHANNEL_ID_STR.startswith("@"):
    # Если передан username канала (например, @channel_name), используем как строку
    CHANNEL_ID = CHANNEL_ID_STR
else:
    # Если передан числовой ID, конвертируем в int
    try:
        CHANNEL_ID = int(CHANNEL_ID_STR) if CHANNEL_ID_STR else None
    except ValueError:
        raise ValueError(f"CHANNEL_ID должен быть числовым ID (например, -1001234567890) или username канала (например, @channel_name), получено: {CHANNEL_ID_STR}")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "-1003370698977"))
THREAD_ID_KVARTIRY = int(os.getenv("THREAD_ID_KVARTIRY", "2"))
THREAD_ID_KOMMERCIA = int(os.getenv("THREAD_ID_KOMMERCIA", "5"))
THREAD_ID_DOMA = int(os.getenv("THREAD_ID_DOMA", "8"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Список администраторов для команд управления контентом
ADMIN_IDS = [int(ADMIN_ID)]  # Можно расширить список при необходимости

if not BOT_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("BOT_TOKEN and OPENAI_API_KEY must be set in .env")

client = OpenAI(api_key=OPENAI_API_KEY)

# ==========================
# Настройки бота и OpenAI
# ==========================

# ==========================
# Инициализация бота
# ==========================
bot = telebot.TeleBot(BOT_TOKEN)

# Глобальные переменные для состояний
user_leads = {}  # Для сбора лидов

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
            model="gpt-4o-mini",
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
# Админские команды управления контент-планом
# ==========================

# Импортируем базу данных для работы с content_plan
from database import db
import asyncio

# Инициализируем подключение к БД
asyncio.run(db.connect())

def check_admin_permissions(user_id: int) -> bool:
    """Проверка прав администратора"""
    return user_id in ADMIN_IDS

@bot.message_handler(commands=["plan"])
def plan_command(message):
    """Показать список ближайших 10 записей content_plan"""
    user_id = message.from_user.id

    if not check_admin_permissions(user_id):
        bot.send_message(message.chat.id, "❌ Недостаточно прав")
        return

    try:
        # Получаем все посты из базы данных
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Получаем все посты (можно оптимизировать, но для админки сойдет)
        posts = loop.run_until_complete(db.get_all_posts(limit=10))

        if not posts:
            bot.send_message(message.chat.id, "📭 Контент-план пуст")
            return

        response = "📋 Ближайшие записи контент-плана:\n\n"

        for post in posts:
            post_date = post.get('publish_date', 'Не указана')
            if isinstance(post_date, str) and 'T' in post_date:
                # Форматируем дату и время
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(post_date.replace('Z', '+00:00'))
                    date_str = dt.strftime('%d.%m.%Y')
                    time_str = dt.strftime('%H:%M')
                except:
                    date_str = post_date.split('T')[0] if 'T' in post_date else post_date
                    time_str = "00:00"
            else:
                date_str = str(post_date)
                time_str = "00:00"

            status = post.get('status', 'unknown')
            post_type = post.get('type', 'unknown')

            response += f"🆔 {post['id']} | 📅 {date_str} {time_str} | 📝 {post_type} | 📊 {status}\n"

        # Ограничиваем длину сообщения Telegram
        if len(response) > 4000:
            response = response[:3950] + "\n\n... (сообщение обрезано)"

        bot.send_message(message.chat.id, response)

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка получения плана: {str(e)}")

@bot.message_handler(commands=["preview"])
def preview_command(message):
    """Показать полный текст поста и метаданные по ID"""
    user_id = message.from_user.id

    if not check_admin_permissions(user_id):
        bot.send_message(message.chat.id, "❌ Недостаточно прав")
        return

    try:
        # Парсим команду: /preview <id>
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Формат: /preview <id>\nПример: /preview 1")
            return

        post_id = int(parts[1])

        # Получаем пост из базы данных
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Ищем пост по ID (простая реализация)
        all_posts = loop.run_until_complete(db.get_all_posts(limit=100))
        post = next((p for p in all_posts if p['id'] == post_id), None)

        if not post:
            bot.send_message(message.chat.id, f"❌ Пост с ID {post_id} не найден")
            return

        # Формируем ответ с метаданными
        response = f"📄 Пост #{post_id}\n\n"

        # Метаданные
        response += f"📝 Тип: {post.get('type', 'Не указан')}\n"
        response += f"📊 Статус: {post.get('status', 'Не указан')}\n"

        publish_date = post.get('publish_date')
        if publish_date:
            if isinstance(publish_date, str) and 'T' in publish_date:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(publish_date.replace('Z', '+00:00'))
                    response += f"📅 Дата публикации: {dt.strftime('%d.%m.%Y %H:%M')}\n"
                except:
                    response += f"📅 Дата публикации: {publish_date}\n"
            else:
                response += f"📅 Дата публикации: {publish_date}\n"

        created_at = post.get('created_at')
        if created_at:
            response += f"🕐 Создан: {created_at}\n"

        published_at = post.get('published_at')
        if published_at:
            response += f"✅ Опубликован: {published_at}\n"

        image_prompt = post.get('image_prompt')
        if image_prompt:
            response += f"🖼️ Промпт изображения: {image_prompt[:100]}{'...' if len(image_prompt) > 100 else ''}\n"

        response += "\n" + "="*50 + "\n\n"

        # Содержимое поста
        title = post.get('title', '').strip()
        body = post.get('body', '').strip()
        cta = post.get('cta', '').strip()

        if title:
            response += f"<b>{title}</b>\n\n"

        if body:
            response += f"{body}\n\n"

        if cta:
            response += f"<b>{cta}</b>"

        # Ограничиваем длину сообщения
        if len(response) > 4000:
            response = response[:3950] + "\n\n... (сообщение обрезано)"

        bot.send_message(message.chat.id, response, parse_mode='HTML')

    except ValueError:
        bot.send_message(message.chat.id, "❌ ID должен быть числом")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка получения поста: {str(e)}")

# Глобальная переменная для отслеживания режима редактирования
edit_mode = {}  # user_id -> post_id

@bot.message_handler(commands=["edit"])
def edit_command(message):
    """Начать редактирование поста по ID"""
    user_id = message.from_user.id

    if not check_admin_permissions(user_id):
        bot.send_message(message.chat.id, "❌ Недостаточно прав")
        return

    try:
        # Парсим команду: /edit <id>
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Формат: /edit <id>\nПример: /edit 1")
            return

        post_id = int(parts[1])

        # Проверяем существование поста
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        all_posts = loop.run_until_complete(db.get_all_posts(limit=100))
        post = next((p for p in all_posts if p['id'] == post_id), None)

        if not post:
            bot.send_message(message.chat.id, f"❌ Пост с ID {post_id} не найден")
            return

        # Включаем режим редактирования
        edit_mode[user_id] = post_id

        # Показываем текущий текст
        current_text = ""
        if post.get('title'):
            current_text += f"<b>{post['title']}</b>\n\n"
        if post.get('body'):
            current_text += f"{post['body']}\n\n"
        if post.get('cta'):
            current_text += f"<b>{post['cta']}</b>"

        if not current_text.strip():
            current_text = "Пост пустой"

        bot.send_message(
            message.chat.id,
            f"✏️ Редактирование поста #{post_id}\n\nТекущий текст:\n{current_text}\n\nОтправьте новый текст поста (можно с HTML-разметкой):",
            parse_mode='HTML'
        )

    except ValueError:
        bot.send_message(message.chat.id, "❌ ID должен быть числом")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")

@bot.message_handler(func=lambda message: message.from_user.id in edit_mode)
def handle_edit_text(message):
    """Обработчик нового текста для редактирования поста"""
    user_id = message.from_user.id
    post_id = edit_mode[user_id]

    try:
        new_text = message.text.strip()

        # Простое разделение на title, body, cta
        lines = new_text.split('\n\n')
        title = ""
        body = ""
        cta = ""

        # Ищем CTA (строки с призывами к действию)
        cta_keywords = ['👉', 'напишите', 'свяжитесь', 'узнайте', 'получите']
        cta_lines = []

        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in cta_keywords):
                cta_lines.extend(lines[i:])
                lines = lines[:i]
                break

        if cta_lines:
            cta = '\n\n'.join(cta_lines)
        else:
            # Если нет явного CTA, берём последнюю строку
            if lines:
                cta = lines.pop()

        # Первая строка может быть заголовком
        if lines and len(lines[0]) < 100:
            title = lines[0]
            body_lines = lines[1:]
        else:
            body_lines = lines

        body = '\n\n'.join(body_lines) if body_lines else ""

        # Сохраняем в базу данных
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        loop.run_until_complete(db.update_content_plan_entry(
            post_id=post_id,
            title=title if title else None,
            body=body if body else None,
            cta=cta if cta else None
        ))

        # Выключаем режим редактирования
        del edit_mode[user_id]

        bot.send_message(
            message.chat.id,
            f"✅ Пост #{post_id} обновлён!\n\n<b>Заголовок:</b> {title or 'Не указан'}\n<b>Текст:</b> {body[:100]}{'...' if len(body) > 100 else ''}\n<b>CTA:</b> {cta or 'Не указан'}",
            parse_mode='HTML'
        )

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка сохранения: {str(e)}")
        # Не выключаем режим редактирования при ошибке


# ==========================
# Запуск бота
# ==========================
print("Бот запущен...")
bot.polling(non_stop=True)
