import telebot
import requests
import datetime
import time
import os
import glob
from telebot import types
from dotenv import load_dotenv

load_dotenv()
from kb_rag import KnowledgeBaseRAG
API_TOKEN = os.getenv('API_TOKEN')
YANDEX_API_KEY = os.getenv('YANDEX_API_KEY')
FOLDER_ID = os.getenv('FOLDER_ID')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
CHANNEL_ID = os.getenv('CHANNEL_ID')

bot = telebot.TeleBot(API_TOKEN)
kb = KnowledgeBaseRAG("uploads")
kb.index_markdown_files()
user_histories = {}
user_names = {}
user_states = {}
UPLOAD_PLANS_DIR = "/root/PARKHOMENKO_BOT/uploads_plans"

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def save_lead_and_notify(user, text, phone=None):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    with open(f"leads_{date_str}.txt", "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] @{user.username} | {user.first_name} | {phone or ''} | {text}\n")
    if phone or any(word in text.lower() for word in ["кухня", "квартира", "дом", "хочу"]):
        msg = (f"🔥 **НОВЫЙ ЛИД: ПАРХОМЕНКО**\n👤 Имя: {user.first_name}\n"
               f"📱 Тел: {phone or 'Не указан'}\n💬 Текст: {text}\n🔗 Юзер: @{user.username or 'отсутствует'}")
        try:
            bot.send_message(CHANNEL_ID, msg, parse_mode="Markdown")
        except:
            pass

@bot.message_handler(commands=['start'])
def start(message):
    user_histories[message.chat.id] = []
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("✅ Согласен с условиями и ПД"))
    bot.send_message(
        message.chat.id,
        "Здравствуйте! Я Антон, ИИ‑ассистент Юлии Пархоменко.\n\n"
        "Перед тем как продолжить, подтвердите, пожалуйста:\n"
        "— согласие на обработку ваших персональных данных;\n"
        "— согласие на получение от нас сообщений и уведомлений.\n\n"
        "Нажимая кнопку ниже, вы даёте оба этих согласия.",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "✅ Согласен с условиями и ПД")
def agreement_accepted(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("📱 Отправить контакт", request_contact=True))
    bot.send_message(message.chat.id, "Нажмите кнопку ниже, чтобы мы закрепили за вами специалиста.", reply_markup=markup)

@bot.message_handler(content_types=['document', 'photo'])
def handle_files(message):
    chat_id = message.chat.id
    user_name = user_names.get(chat_id, message.from_user.first_name)

    # Инициализируем состояние, если его ещё нет
    if chat_id not in user_states:
        user_states[chat_id] = {}

    try:
        # Определяем файл
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            ext = ".jpg"
        else:
            file_id = message.document.file_id
            # можно аккуратно вытащить расширение из имени документа
            ext = "." + (message.document.file_name.split(".")[-1] if "." in message.document.file_name else "bin")

        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        filename = f"{chat_id}_{int(datetime.datetime.now().timestamp())}{ext}"
        path = f"{UPLOAD_PLANS_DIR}/{filename}"

        with open(path, 'wb') as f:
            f.write(downloaded_file)

        # Помечаем, что у пользователя есть план
        user_states[chat_id]['has_plan'] = True
        user_states[chat_id]['last_plan_path'] = path

        # Уведомляем администратора, как раньше
        bot.send_message(ADMIN_ID, f"📎 План квартиры от {user_name}: {path}")
        bot.forward_message(ADMIN_ID, chat_id, message.message_id)

        # Сообщение клиенту — в духе нового сценария
        bot.send_message(
            chat_id,
            (
                f"{user_name}, спасибо за план квартиры — по нему уже можно точнее сориентироваться. "
                "Сейчас задам пару вопросов, чтобы понять вашу ситуацию и при необходимости передать её эксперту.\n\n"
                "Скажите, пожалуйста:\n"
                "1) Примерная площадь квартиры?\n"
                "2) Сколько человек в ней живёт (один, пара, семья с детьми)?\n"
                "3) Зачем хотите именно такую перепланировку — что хотите получить в итоге?"
            )
        )

    except Exception as e:
        print(f"Error saving file: {e}")
        bot.send_message(chat_id, "Не удалось сохранить файл. Попробуйте, пожалуйста, ещё раз или пришлите его в другом формате.")

@bot.message_handler(content_types=['contact', 'text'])
def handle_messages(message):
    user_id = message.chat.id
    if message.content_type == 'contact':
        user_names[user_id] = message.contact.first_name
        save_lead_and_notify(message.from_user, "Оставил контакт", message.contact.phone_number)
        bot.send_message(user_id, f"Приятно познакомиться, {user_names[user_id]}! Какой объект планируете перепланировать (квартира или коммерция)?")
        return
    user_name = user_names.get(user_id, message.from_user.first_name)
    save_lead_and_notify(message.from_user, message.text)
    answer = ask_yandex_gpt(user_id, message.text, user_name)
    bot.send_message(user_id, answer)

def ask_yandex_gpt(user_id, user_text, user_name):
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {"Authorization": f"Api-Key {YANDEX_API_KEY}", "Content-Type": "application/json"}
    if user_id not in user_histories:
        user_histories[user_id] = []
    user_histories[user_id].append({"role": "user", "text": user_text})
    context = kb.get_context(user_text)
    has_plan = user_states.get(user_id, {}).get('has_plan', False)

    # Формируем инструкцию/контекст для Yandex GPT
    extra_context_parts = []

    if has_plan:
        extra_context_parts.append(
            "Важно: пользователь уже прислал план квартиры. "
            "Ты не видишь картинку, но знаешь, что план есть. "
            "Сначала задай по одному вопросы про площадь квартиры, состав семьи и цель перепланировки. "
            "Затем дай предварительный вывод по общим нормам и предложи передать ситуацию эксперту команды."
        )

    extra_context = "\n".join(extra_context_parts)

    instruction = (
        f"Ты — Антон, эксперт Юлии Пархоменко. Собеседник: {user_name}. "
        "ПРАВИЛА: 1. Обращайся по имени: {user_name}. 2. Один вопрос за раз. "
        "3. Если кухня+комната — спроси про ГАЗ. При газе объединение запрещено без перегородки. "
        "4. Спрашивай: город, статус (уже сделано или нет), этаж/этажность. "
        "5. Проси только улицу и дом (без квартиры) для серии дома. "
        "6. Про план БТИ спроси в конце."
        f"Контекст из базы знаний: {context}"
        f"{extra_context}"
    )
    data = {
        "modelUri": f"gpt://{FOLDER_ID}/yandexgpt/latest",
        "completionOptions": {"temperature": 0.2, "maxTokens": 500},
        "messages": [{"role": "system", "text": instruction}] + user_histories[user_id][-10:]
    }
    try:
        res = requests.post(url, headers=headers, json=data, timeout=30)
        ai_text = res.json()["result"]["alternatives"][0]["message"]["text"]
        user_histories[user_id].append({"role": "assistant", "text": ai_text})
        return ai_text
    except Exception as e:
        return f"{user_name}, уточните, пожалуйста, детали объекта."

print("Запуск бота...")
while True:
    try:
        bot.polling(none_stop=True, timeout=60)
    except Exception as e:
        print(f"Polling error: {e}")
        time.sleep(15)
