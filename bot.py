# bot.py — консультант по перепланировкам
import os
import requests
import telebot
from dotenv import load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
FOLDER_ID = os.getenv("FOLDER_ID")

LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "-1003370698977"))
THREAD_ID_KVARTIRY = int(os.getenv("THREAD_ID_KVARTIRY", "2"))
THREAD_ID_KOMMERCIA = int(os.getenv("THREAD_ID_KOMMERCIA", "5"))
THREAD_ID_DOMA = int(os.getenv("THREAD_ID_DOMA", "8"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN must be set in .env")
if not YANDEX_API_KEY or not FOLDER_ID:
    raise RuntimeError("YANDEX_API_KEY and FOLDER_ID must be set in .env")

bot = telebot.TeleBot(BOT_TOKEN)

# временное хранилище лида
user_leads: dict[int, dict] = {}

# ----------------- YandexGPT -----------------


def ya_generate_text(prompt: str) -> str:
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Authorization": f"Api-Key {YANDEX_API_KEY}",
        "Content-Type": "application/json",
    }
    data = {
        "modelUri": f"gpt://{FOLDER_ID}/yandexgpt-lite/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.2,
            "maxTokens": 800,
        },
        "messages": [
            {
                "role": "user",
                "text": (
                    "Ты — юрист и проектировщик по перепланировкам квартир, домов и "
                    "коммерческих помещений в России. Отвечай кратко, по делу, без "
                    "воды, понятным языком для собственника жилья.\n\n"
                    f"Вопрос клиента: {prompt}"
                ),
            }
        ],
    }

    try:
        resp = requests.post(url, headers=headers, json=data, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        return result["result"]["alternatives"][0]["message"]["text"]
    except Exception as e:
        return f"Не получилось получить ответ от ЯндексGPT: {e}"


# ----------------- Отправка лида -----------------


def send_lead_to_group(summary_text: str, object_type: str):
    if object_type == "квартира":
        thread_id = THREAD_ID_KVARTIRY
    elif object_type == "коммерция":
        thread_id = THREAD_ID_KOMМERCIA
    elif object_type == "дом":
        thread_id = THREAD_ID_DOMА
    else:
        thread_id = None

    bot.send_message(
        chat_id=LEADS_GROUP_CHAT_ID,
        text=f"🔥 НОВАЯ ЗАЯВКА ПО ПЕРЕПЛАНИРОВКЕ\n\n{summary_text}",
        message_thread_id=thread_id,
    )


# ----------------- Старт и меню -----------------


@bot.message_handler(commands=["start"])
def start(message):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(
            "Консультация по перепланировке",
            callback_data="collect_lead",
        )
    )
    bot.send_message(
        message.chat.id,
        "Здравствуйте! Помогу с перепланировкой квартиры, дома или коммерции.\n\n"
        "Нажмите кнопку, чтобы оставить заявку, и я задам несколько вопросов.",
        reply_markup=markup,
    )


@bot.message_handler(commands=["ask"])
def ask_expert(message):
    bot.send_message(
        message.chat.id,
        "Опишите свой вопрос по перепланировке (что хотите сделать, какой город):",
    )
    bot.register_next_step_handler(message, handle_expert_question)


def handle_expert_question(message):
    answer = ya_generate_text(message.text)
    bot.send_message(message.chat.id, answer)


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id

    if call.data == "collect_lead":
        bot.send_message(
            chat_id,
            "Перед началом нужно ваше согласие на обработку персональных данных "
            "и получение от нас сообщений.\n\n"
            "Если согласны — напишите «да».",
        )
        bot.register_next_step_handler(call.message, ask_name)

    elif call.data.startswith("obj_"):
        object_type = call.data.replace("obj_", "")
        if object_type == "kvartira":
            obj = "квартира"
        elif object_type == "kommertsia":
            obj = "коммерция"
        elif object_type == "dom":
            obj = "дом"
        else:
            obj = "объект"

        if chat_id not in user_leads:
            user_leads[chat_id] = {}

        user_leads[chat_id]["object_type"] = obj
        bot.send_message(chat_id, "Укажите город/регион:")
        bot.register_next_step_handler(call.message, ask_city)


# ----------------- Сценарий сбора лида -----------------


def ask_name(message):
    chat_id = message.chat.id
    if message.text.lower().strip() not in ["да", "yes"]:
        bot.send_message(
            chat_id,
            "Без согласия на обработку персональных данных продолжить нельзя.",
        )
        return

    user_leads[chat_id] = {"pd_agreed": True}
    bot.send_message(chat_id, "Как к вам обращаться?")
    bot.register_next_step_handler(message, ask_phone)


def ask_phone(message):
    chat_id = message.chat.id
    lead = user_leads.get(chat_id, {})
    lead["name"] = message.text.strip()
    user_leads[chat_id] = lead

    bot.send_message(
        chat_id,
        "Укажите номер телефона для связи (можно WhatsApp/Telegram):",
    )
    bot.register_next_step_handler(message, ask_object_type_inline)


def ask_object_type_inline(message):
    chat_id = message.chat.id
    lead = user_leads.get(chat_id, {})
    lead["phone"] = message.text.strip()
    user_leads[chat_id] = lead

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Квартира", callback_data="obj_kvartira"))
    markup.add(
        InlineKeyboardButton("Коммерция", callback_data="obj_kommertsia")
    )
    markup.add(InlineKeyboardButton("Дом", callback_data="obj_dom"))
    bot.send_message(chat_id, "Выберите тип объекта:", reply_markup=markup)


def ask_city(message):
    chat_id = message.chat.id
    lead = user_leads.get(chat_id, {})
    lead["city"] = message.text.strip()
    user_leads[chat_id] = lead

    bot.send_message(
        chat_id,
        "Кратко опишите, что хотите изменить в перепланировке "
        "(объединить комнаты, перенести санузел, расширить кухню и т.п.).",
    )
    bot.register_next_step_handler(message, ask_change_plan)


def ask_change_plan(message):
    chat_id = message.chat.id
    lead = user_leads.get(chat_id, {})
    lead["change_plan"] = message.text.strip()
    user_leads[chat_id] = lead

    bot.send_message(
        chat_id,
        "Есть ли у вас сейчас на руках документы БТИ по этому объекту "
        "(поэтажный план, экспликация, техпаспорт)? "
        "Кратко опишите: есть/нет, в каком виде.",
    )
    bot.register_next_step_handler(message, finalize_lead)


def finalize_lead(message):
    chat_id = message.chat.id
    lead = user_leads.get(chat_id, {})
    lead["bti_status"] = message.text.strip()
    user_leads[chat_id] = lead

    summary = (
        f"Имя: {lead.get('name')}\n"
        f"Телефон: {lead.get('phone')}\n"
        f"Тип объекта: {lead.get('object_type')}\n"
        f"Город/регион: {lead.get('city')}\n"
        f"Что хочет изменить: {lead.get('change_plan')}\n"
        f"Статус документов БТИ: {lead.get('bti_status')}"
    )

    send_lead_to_group(summary, lead.get("object_type", "объект"))
    bot.send_message(
        chat_id,
        "Спасибо, информация получена. Заявка передана специалисту. "
        "Адрес и детали по документам уточним уже в личном общении.",
    )

    user_leads.pop(chat_id, None)


# ----------------- Запуск -----------------

if __name__ == "__main__":
    print("Бот по перепланировкам запущен...")
    bot.polling(non_stop=True, timeout=60)
