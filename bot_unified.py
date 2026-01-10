import os
import time
import datetime
import requests
import telebot
from telebot import types
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
FOLDER_ID = os.getenv("FOLDER_ID")

LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "0"))
THREAD_ID_KVARTIRY = int(os.getenv("THREAD_ID_KVARTIRY", "0"))
THREAD_ID_KOMMERCIA = int(os.getenv("THREAD_ID_KOMMERCIA", "0"))
THREAD_ID_DOMA = int(os.getenv("THREAD_ID_DOMA", "0"))

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Пути для файлов
UPLOAD_PLANS_DIR = os.getenv("UPLOAD_PLANS_DIR", "uploads_plans")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
KNOWLEDGE_DIR = "knowledge_base"

os.makedirs(UPLOAD_PLANS_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(KNOWLEDGE_DIR, exist_ok=True)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN must be set in .env")
if not YANDEX_API_KEY or not FOLDER_ID:
    raise RuntimeError("YANDEX_API_KEY and FOLDER_ID must be set in .env")

bot = telebot.TeleBot(BOT_TOKEN)

# --------- RAG ---------
try:
    from kb_rag import KnowledgeBaseRAG
    kb = KnowledgeBaseRAG(KNOWLEDGE_DIR)
    kb.index_markdown_files()
    print(f"✅ База знаний загружена из: {KNOWLEDGE_DIR}")
except ImportError:
    print("⚠️ Модуль kb_rag не найден, RAG отключен")
    kb = None
except Exception as e:
    print(f"❌ Ошибка загрузки базы знаний: {e}")
    kb = None

# --------- Состояния ---------

class BotModes:
    QUIZ = "quiz"
    DIALOG = "dialog"
    QUICK = "quick"

class UserConsent:
    def __init__(self):
        self.privacy_accepted = False
        self.notifications_accepted = False
        self.ai_disclaimer_seen = False
        self.consent_timestamp = None
        self.contact_received = False
        self.name_confirmed = False

class UserState:
    def __init__(self):
        self.name = None
        self.phone = None
        self.extra_contact = None

        self.mode = None
        self.quiz_step = 0

        self.object_type = None
        self.city = None
        self.bti_status = None

        # новые поля — ВНУТРИ __init__, с тем же отступом
        self.floor = None
        self.total_floors = None
        self.remodeling_status = None  # выполнена или планируется

        self.dialog_history = []
        self.has_plan = False
        self.plan_path = None
        self.change_plan = None

user_states: dict[int, UserState] = {}
user_consents: dict[int, UserConsent] = {}

# --------- Тексты ---------

PRIVACY_POLICY_TEXT = (
    "📋 Добро пожаловать в сервис консультаций по перепланировке "
    "«Пархоменко и компания»!\n\n"
    "Перед началом работы необходимо:\n"
    "✅ Согласие на обработку персональных данных\n"
    "✅ Согласие на получение уведомлений\n\n"
    "Наш AI-консультант Антон поможет вам, но помните:\n"
    "• Консультации носят информационный характер\n"
    "• Мы соблюдаем законодательство РФ"
)

AI_INTRO_TEXT = (
    "🤖 Вас приветствует Антон, AI‑консультант по перепланировкам "
    "в команде «Пархоменко и компания».\n\n"
    "Я могу:\n"
    "• Ответить на вопросы по нормам и требованиям\n"
    "• Помочь с оформлением заявки\n"
    "• Проанализировать план помещения\n\n"
    "⚠️ Важно: мои рекомендации носят информационный характер. "
    "Наш специалист даст вам полную информацию по документации."
)

# --------- Утилиты ---------

def get_user_state(user_id: int) -> UserState:
    if user_id not in user_states:
        user_states[user_id] = UserState()
    return user_states[user_id]

def get_user_consent(user_id: int) -> UserConsent:
    if user_id not in user_consents:
        user_consents[user_id] = UserConsent()
    return user_consents[user_id]

def add_legal_disclaimer(text: str) -> str:
    disclaimer = (
        "\n\n⚠️ Важно: данная информация носит ознакомительный характер. "
        "Наш специалист даст вам полную информацию по документации."
    )
    return text + disclaimer

def show_privacy_consent(chat_id: int):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("✅ Я согласен и хочу продолжить"))
    markup.add(types.KeyboardButton("❌ Отказаться"))
    bot.send_message(chat_id, PRIVACY_POLICY_TEXT, reply_markup=markup)

def show_ai_disclaimer(chat_id: int):
    bot.send_message(chat_id, AI_INTRO_TEXT)

def show_main_menu(chat_id: int):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📝 Оставить заявку", callback_data="mode_quiz"))
    markup.add(types.InlineKeyboardButton("💬 Задать вопрос эксперту", callback_data="mode_dialog"))
    markup.add(types.InlineKeyboardButton("⚡ Быстрая консультация", callback_data="mode_quick"))
    bot.send_message(chat_id, "Выберите, чем Антон может помочь:", reply_markup=markup)

# --------- Лиды ---------

def save_lead_and_notify(user_id: int):
    state = get_user_state(user_id)

    lead_info = f"""
📋 Новая заявка на перепланировку

👤 Имя: {state.name}
📞 Телефон (TG): {state.phone}
📪 Доп. контакт: {state.extra_contact or 'не указан'}
🏠 Тип объекта: {state.object_type or 'не выбран'}
� Город: {state.city or 'не указан'}
� Что хочет изменить: {state.change_plan or 'не указано'}
📄 Статус БТИ: {state.bti_status or 'не указан'}
🕐 Время: {datetime.datetime.now().strftime("%d.%m.%Y %H:%M")}
👤 User ID: {user_id}
    """.strip()

    if state.object_type == "Квартира":
        thread_id = THREAD_ID_KVARTIRY
    elif state.object_type == "Коммерция":
        thread_id = THREAD_ID_KOMMERCIA
    elif state.object_type == "Дом":
        thread_id = THREAD_ID_DOMA
    else:
        thread_id = None

    try:
        if thread_id:
            bot.send_message(LEADS_GROUP_CHAT_ID, lead_info, message_thread_id=thread_id)
        else:
            bot.send_message(LEADS_GROUP_CHAT_ID, lead_info)
        print(f"✅ Лид отправлен в группу: {state.name}, {state.phone}")
    except Exception as e:
        print(f"❌ Ошибка отправки лида: {e}")
        try:
            bot.send_message(ADMIN_ID, f"❌ Ошибка отправки лида: {e}\n\n{lead_info}")
        except:
            pass

def save_dialog_lead(chat_id: int, dialog_summary: str):
    state = get_user_state(chat_id)

    lead_info = f"""
💬 Консультация в диалоговом режиме

👤 Имя: {state.name}
📞 Телефон: {state.phone}
📝 Тема: {dialog_summary}
🕐 Время: {datetime.datetime.now().strftime("%d.%m.%Y %H:%M")}
👤 User ID: {chat_id}

⚠️ Клиент получил консультацию, но не оставил полную заявку
    """.strip()

    try:
        bot.send_message(LEADS_GROUP_CHAT_ID, lead_info)
        print(f"✅ Диалог-лид отправлен: {state.name}")
    except Exception as e:
        print(f"❌ Ошибка отправки диалог-лида: {e}")

def generate_manager_brief(chat_id: int) -> str:
    """Генерирует пояснительную записку для менеджера на основе диалога"""
    state = get_user_state(chat_id)

    if not state.dialog_history:
        return "Диалог пуст"

    # Собираем все вопросы клиента
    client_messages = [h['text'] for h in state.dialog_history if h['role'] == 'user']

    # Формируем полный текст диалога для анализа
    full_dialog = "\n".join([f"{'Клиент' if h['role'] == 'user' else 'Антон'}: {h['text']}"
                            for h in state.dialog_history])

    # Запрашиваем у YandexGPT анализ диалога
    analysis_prompt = f"""
Проанализируй диалог с клиентом и выдели:
1. Основной запрос клиента (кратко, 1-2 предложения)
2. Выявленные потребности (список из 3-5 пунктов)
3. Важные детали для менеджера (что нужно уточнить, на что обратить внимание)

Диалог:
{full_dialog}

Ответь структурированно по пунктам 1, 2, 3.
"""

    analysis = call_yandex_gpt(analysis_prompt, model="yandexgpt-lite")

    brief = f"""
📋 Пояснительная записка по лиду

👤 Клиент: {state.name} ({state.phone})
📝 Первичный запрос: {client_messages[0] if client_messages else 'не указан'}

{analysis}

📞 Рекомендация: Связаться в удобное для клиента время
    """.strip()

    return brief

# --------- YandexGPT + RAG ---------

def call_yandex_gpt(prompt: str, user_name: str = None, model: str = "yandexgpt") -> str:
    try:
        headers = {
            "Authorization": f"Api-Key {YANDEX_API_KEY}",
            "Content-Type": "application/json"
        }

        greeting = f"{user_name}, " if user_name else ""

        data = {
            "modelUri": f"gpt://{FOLDER_ID}/{model}/latest",
            "completionOptions": {
                "stream": False,
                "temperature": 0.2,
                "maxTokens": 400
            },
            "messages": [
                {
                    "role": "system",
                    "text": (
                        "Ты - Антон, AI-консультант по перепланировкам в компании «Пархоменко и компания». "
                        "\n\nКРИТИЧЕСКИ ВАЖНО:\n\n"
                        "1. РАБОТА С БАЗОЙ ЗНАНИЙ:\n"
                        "- ИСПОЛЬЗУЙ ТОЛЬКО информацию из базы знаний (контекст в промпте)\n"
                        "- НЕ выдумывай и НЕ додумывай информацию\n"
                        "- Если информации нет в базе — дай общий ответ на основе своих знаний о перепланировках\n\n"
                        "2. СТИЛЬ ОТВЕТОВ:\n"
                        "- Максимум 2-3 предложения (не больше!)\n"
                        "- Конкретно и по делу, без 'воды'\n"
                        "- НЕ задавай лишних вопросов про дизайн/стиль, если клиент про юридику\n\n"
                        "3. ЛОГИКА КОНСУЛЬТАЦИИ:\n"
                        "- Если клиент спрашивает про документы/согласование — кратко перечисли этапы из базы\n"
                        "- После 2-х ответов предлагай оставить заявку для детальной консультации\n\n"
                        "4. ПЕРЕХОД К СПЕЦИАЛИСТУ:\n"
                        "- Если клиент просит связать со специалистом — подтверди и уточни удобное время\n\n"
                        f"5. Обращайся по имени: {greeting if user_name else ''}"
                    )
                },
                {
                    "role": "user",
                    "text": prompt
                }
            ]
        }

        response = requests.post(
            "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
            headers=headers,
            json=data,
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            return result["result"]["alternatives"][0]["message"]["text"]
        else:
            return f"Ошибка API ЯндексGPT: {response.status_code}"

    except Exception as e:
        return f"Ошибка подключения к ЯндексGPT: {str(e)}"

def get_rag_context(question: str) -> str:
    if not kb:
        return "База знаний временно недоступна."
    try:
        return kb.get_rag_context(question)
    except Exception as e:
        return f"Ошибка поиска в базе знаний: {e}"

def ask_yandex_gpt_with_context(question: str, context: str = "", user_name: str = None) -> str:
    prompt = f"""
Контекст из базы знаний:
{context}

Вопрос: {question}

Дай короткий конкретный ответ (2-3 абзаца) и задай уточняющий вопрос для продолжения диалога.
"""
    return call_yandex_gpt(prompt, user_name=user_name)

# --------- Хэндлеры согласий ---------

@bot.message_handler(commands=["start"])
def start_handler(message):
    user_id = message.chat.id
    consent = get_user_consent(user_id)

    if not consent.privacy_accepted:
        show_privacy_consent(user_id)
        return

    if not consent.ai_disclaimer_seen:
        show_ai_disclaimer(user_id)
        consent.ai_disclaimer_seen = True
        consent.consent_timestamp = datetime.datetime.now()
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton("📱 Поделиться контактом", request_contact=True))
        bot.send_message(
            user_id,
            "Для продолжения работы поделитесь своим контактом Telegram — это защитит нас от спама и поможет быстрее связаться.",
            reply_markup=markup
        )
        return

    if not consent.contact_received:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton("📱 Поделиться контактом", request_contact=True))
        bot.send_message(
            user_id,
            "Для продолжения работы поделитесь своим контактом Telegram.",
            reply_markup=markup
        )
        return

    show_main_menu(user_id)

@bot.message_handler(commands=["privacy"])
def privacy_info(message):
    show_privacy_consent(message.chat.id)

@bot.message_handler(func=lambda m: m.text in ["✅ Я согласен и хочу продолжить", "❌ Отказаться"])
def privacy_consent_handler(message):
    user_id = message.chat.id
    consent = get_user_consent(user_id)

    if "Отказаться" in message.text:
        bot.send_message(user_id, "Без согласия на обработку данных использовать бота нельзя.")
        return

    consent.privacy_accepted = True
    consent.notifications_accepted = True
    consent.consent_timestamp = datetime.datetime.now()
    show_ai_disclaimer(user_id)
    consent.ai_disclaimer_seen = True
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("📱 Поделиться контактом", request_contact=True))
    bot.send_message(
        user_id,
        "Для продолжения работы поделитесь своим контактом Telegram — это защитит нас от спама и поможет быстрее связаться.",
        reply_markup=markup
    )

@bot.message_handler(content_types=["contact"], func=lambda m: get_user_consent(m.chat.id).privacy_accepted and not get_user_consent(m.chat.id).contact_received)
def initial_contact_handler(message):
    user_id = message.chat.id
    state = get_user_state(user_id)
    consent = get_user_consent(user_id)
    
    state.phone = message.contact.phone_number
    consent.contact_received = True
    
    # Извлекаем имя из контакта
    contact_name = message.contact.first_name or ""
    
    hide_kb = types.ReplyKeyboardRemove()
    
    if contact_name:
        # Если имя есть — предлагаем подтвердить
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(f"✅ Да, {contact_name}", callback_data=f"confirm_name_{contact_name}"))
        markup.add(types.InlineKeyboardButton("✏️ Нет, указать другое", callback_data="change_name"))
        
        bot.send_message(
            user_id,
            f"Спасибо! Ваш контакт {state.phone} сохранён.\n\n"
            f"Могу к вам обращаться «{contact_name}»?",
            reply_markup=markup
        )
    else:
        # Если имени нет — спрашиваем
        bot.send_message(
            user_id,
            f"Спасибо! Ваш контакт {state.phone} сохранён.\n\nКак к вам обращаться?",
            reply_markup=hide_kb
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_name_") or call.data == "change_name")
def name_confirmation_handler(call):
    user_id = call.message.chat.id
    state = get_user_state(user_id)
    
    if call.data.startswith("confirm_name_"):
        # Подтверждение имени
        name = call.data.replace("confirm_name_", "")
        state.name = name
        bot.edit_message_text(
            f"Приятно познакомиться, {name}!",
            chat_id=user_id,
            message_id=call.message.message_id
        )
        show_main_menu(user_id)
        
    elif call.data == "change_name":
        # Запрос нового имени
        bot.edit_message_text(
            "Хорошо, напишите, как к вам обращаться:",
            chat_id=user_id,
            message_id=call.message.message_id
        )

@bot.message_handler(func=lambda m: get_user_consent(m.chat.id).contact_received and get_user_state(m.chat.id).name is None and get_user_state(m.chat.id).mode is None, content_types=["text"])
def initial_name_handler(message):
    user_id = message.chat.id
    state = get_user_state(user_id)

    state.name = message.text.strip()
    bot.send_message(user_id, f"Приятно познакомиться, {state.name}!")
    show_main_menu(user_id)

@bot.message_handler(func=lambda m: get_user_state(m.chat.id).mode == "waiting_time",
                     content_types=["text"])
def time_handler(message):
    chat_id = message.chat.id
    state = get_user_state(chat_id)

    preferred_time = message.text.strip()

    lead_update = f"""
📞 Уточнение времени звонка

👤 {state.name} ({state.phone})
🕐 Удобное время: {preferred_time}
    """.strip()

    try:
        bot.send_message(LEADS_GROUP_CHAT_ID, lead_update)
    except Exception as e:
        print(f"❌ Ошибка отправки времени: {e}")

    bot.send_message(
        chat_id,
        f"Спасибо, {state.name}! Мы свяжемся с вами в указанное время."
    )

    state.mode = None

# ========== CALLBACK HANDLER: Выбор режимов и объектов ==========

@bot.callback_query_handler(func=lambda call: call.data.startswith("mode_") or call.data.startswith("obj_"))
def mode_select_handler(call):
    user_id = call.message.chat.id
    consent = get_user_consent(user_id)
    if not consent.privacy_accepted:
        show_privacy_consent(user_id)
        return

    state = get_user_state(user_id)

    # Выбор режима работы
    if call.data == "mode_quiz":
        state.mode = BotModes.QUIZ
        state.quiz_step = 2  # Начинаем с шага 2, имя уже есть
        bot.send_message(
            user_id, 
            "Если у вас есть дополнительный способ связи (WhatsApp/почта/другой номер) — напишите его, или отправьте «нет»."
        )
        
    elif call.data == "mode_dialog":
        state.mode = BotModes.DIALOG
        bot.send_message(user_id, f"{state.name}, опишите вашу ситуацию по перепланировке.")
        
    elif call.data == "mode_quick":
        state.mode = BotModes.QUICK
        bot.send_message(user_id, f"{state.name}, напишите свой вопрос.")
    
    # Выбор типа объекта в квизе
    elif call.data.startswith("obj_") and state.mode == BotModes.QUIZ:
        if call.data == "obj_kvartira":
            state.object_type = "Квартира"
        elif call.data == "obj_kommertsia":
            state.object_type = "Коммерция"
        elif call.data == "obj_dom":
            state.object_type = "Дом"
        else:
            state.object_type = "Неизвестно"

        state.quiz_step = 4
        bot.send_message(user_id, "Укажите город/регион:")
# ========== КВИЗ: Сбор заявки ==========

@bot.message_handler(func=lambda m: get_user_state(m.chat.id).mode == BotModes.QUIZ,
                     content_types=["text"])
def quiz_handler(message):
    chat_id = message.chat.id
    state = get_user_state(chat_id)

    # Шаг 2: дополнительный контакт (опционально)
    if state.quiz_step == 2:
        text = message.text.strip()
        state.extra_contact = None if text.lower() == "нет" else text
        state.quiz_step = 3

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Квартира", callback_data="obj_kvartira"))
        markup.add(types.InlineKeyboardButton("Коммерция", callback_data="obj_kommertsia"))
        markup.add(types.InlineKeyboardButton("Дом", callback_data="obj_dom"))

        bot.send_message(chat_id, "Выберите тип объекта:", reply_markup=markup)
        return

    # Шаг 4: город/регион (после выбора объекта через callback)
    if state.quiz_step == 4:
        state.city = message.text.strip()
        state.quiz_step = 5
        bot.send_message(
            chat_id,
            "Укажите этаж и этажность дома (например: 5/9 или просто 5):"
        )
        return

    # Шаг 5: этаж/этажность дома
    if state.quiz_step == 5:
        parts = message.text.strip().split('/')
        if len(parts) >= 2:
            state.floor = parts[0].strip()
            state.total_floors = parts[1].strip()
        else:
            state.floor = message.text.strip()
            state.total_floors = None

        state.quiz_step = 6
        bot.send_message(
            chat_id,
            "Перепланировка уже выполнена или только планируете? Напишите 'выполнена' или 'планируется'."
        )
        return

    # Шаг 6: статус перепланировки
    if state.quiz_step == 6:
        state.remodeling_status = message.text.strip()
        state.quiz_step = 7
        bot.send_message(
            chat_id,
            "Кратко опишите, что хотите изменить в перепланировке (объединить комнаты, перенести санузел, расширить кухню и т.п.)."
        )
        return

    # Шаг 7: описание изменений
    if state.quiz_step == 7:
        state.change_plan = message.text.strip()
        state.quiz_step = 8
        bot.send_message(
            chat_id,
            "Есть ли у вас сейчас на руках документы БТИ (поэтажный план, экспликация, техпаспорт)? Опишите: есть/нет, что именно."
        )
        return

    # Шаг 8: статус документов БТИ + завершение квиза
    if state.quiz_step == 8:
        state.bti_status = message.text.strip()
        save_lead_and_notify(chat_id)
        bot.send_message(
            chat_id,
            f"✅ Спасибо, {state.name}! Ваша заявка на перепланировку {state.object_type.lower()} принята.\n"
            f"Наш специалист свяжется с вами по номеру {state.phone} в ближайшее время."
        )
        # Сброс состояния БЕЗ показа меню
        state.mode = None
        state.quiz_step = 0
        return

# ========== ДИАЛОГОВЫЙ РЕЖИМ ==========

@bot.message_handler(func=lambda m: get_user_state(m.chat.id).mode == BotModes.DIALOG,
                     content_types=["text"])
def dialog_handler(message):
    chat_id = message.chat.id
    state = get_user_state(chat_id)
    consent = get_user_consent(chat_id)
    if not consent.privacy_accepted:
        show_privacy_consent(chat_id)
        return

    # Проверка на запрос связи с человеком
    trigger_words = ["соедините", "специалист", "менеджер", "человек", "живой", "реальный", "заказать", "связаться"]
    if any(word in message.text.lower() for word in trigger_words):
        # Генерируем пояснительную записку для менеджера
        if len(state.dialog_history) > 0:
            manager_brief = generate_manager_brief(chat_id)
            try:
                bot.send_message(LEADS_GROUP_CHAT_ID, manager_brief)
                print(f"✅ Пояснительная записка отправлена для {state.name}")
            except Exception as e:
                print(f"❌ Ошибка отправки записки: {e}")

        bot.send_message(
            chat_id,
            f"{state.name}, отлично! Наш специалист свяжется с вами по номеру {state.phone}.\n\n"
            "Укажите, пожалуйста, в какое время вам удобно принять звонок?"
        )
        state.mode = "waiting_time"
        return

    # Сохраняем вопрос в историю
    state.dialog_history.append({"role": "user", "text": message.text})

    # Получаем контекст из RAG
    rag_context = get_rag_context(message.text)

    # Формируем историю диалога
    history_text = ""
    if len(state.dialog_history) > 1:
        recent_history = state.dialog_history[-6:-1]
        history_text = "\n".join([f"{'Клиент' if h['role'] == 'user' else 'Антон'}: {h['text']}"
                                  for h in recent_history])

    system_prompt = """
Ты — ИИ‑консультант компании, которая профессионально занимается согласованием перепланировок квартир и помещений,
узакониванием уже выполненных работ и сопровождением сделок с объектами, где есть перепланировка.

Твоя задача:
- Понять ситуацию клиента: что уже сделано или планируется.
- Объяснить простым языком, что обычно согласуемо, а что рискованно.
- Подсказать общую последовательность действий (без инструкций по строительным работам).
- Мягко вести к следующему шагу: чек-лист, консультация, услуга «под ключ».

Источники знаний:
1. В первую очередь опирайся на контекст из базы знаний ниже: нормативка, процедуры, технические разделы, FAQ и сценарии.
2. Если в контексте нет прямого ответа, используй общие знания, но не противоречь базе.
3. Всегда уточняй недостающие данные, если от них зависит вывод (тип дома, этаж, мокрые зоны и т.д.).

Ограничения:
- Не обещай «100% согласуемо» и «точно без рисков».
- Не давай строительных инструкций (как сносить стены и т.п.).
- Не называй точные суммы штрафов и сроков без контекста региона.

Формат ответа:
- Общий лимит — примерно 400–550 символов.
- В начале 1 короткое предложение с выводом по ситуации клиента.
- Далее 1–2 очень коротких абзаца или список из 2–3 пунктов: что важно уточнить и какие есть общие ограничения.
- Заверши 1–2 вопросами для уточнения ситуации (город, тип дома, что именно меняли) ИЛИ аккуратным предложением консультации,
  не давая обещаний результата.
""".strip()

    full_prompt = f"""
{system_prompt}

================ КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ ================
{rag_context}

{f"ПРЕДЫДУЩИЙ ДИАЛОГ:\n{history_text}\n" if history_text else ""}

ТЕКУЩИЙ ВОПРОС КЛИЕНТА:
{message.text}

ИНСТРУКЦИИ ПО ОТВЕТУ:
1. В первую очередь используй КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ выше. Если там есть готовые ответы или похожие сценарии, следуй им по смыслу, но не копируй текст дословно.
2. Если контекст покрывает вопрос частично, дополни ответ общими знаниями о перепланировках, не противореча базе.
3. НЕ повторяй дословно то, что уже было сказано в ПРЕДЫДУЩЕМ ДИАЛОГЕ.
4. Если по контексту можно сделать предварительный вывод (можно/нельзя узаконить, что рискованно) — обязательно сделай его.
5. Весь ответ должен умещаться примерно в 400-550 символов.
6. Делай упор на уточняющие вопросы и аккуратную оценку рисков, не давай гарантий и обещаний.
7. В конце можешь предложить консультацию со специалистом, но только ПОСЛЕ ответа и вопросов.
"""

    response = call_yandex_gpt(full_prompt, user_name=state.name)

    state.dialog_history.append({"role": "assistant", "text": response})
    bot.send_message(chat_id, response)

    # После 3-х вопросов — записка + предложение заявки
    user_messages_count = len([h for h in state.dialog_history if h['role'] == 'user'])
    if user_messages_count == 3:
        manager_brief = generate_manager_brief(chat_id)
        try:
            bot.send_message(LEADS_GROUP_CHAT_ID, manager_brief)
        except Exception as e:
            print(f"❌ Ошибка отправки записки: {e}")

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("📝 Оставить заявку", callback_data="mode_quiz"))
        bot.send_message(
            chat_id,
            f"{state.name}, для детального расчёта и консультации оставьте заявку:",
            reply_markup=markup
        )

# ========== БЫСТРАЯ КОНСУЛЬТАЦИЯ ==========

@bot.message_handler(func=lambda m: get_user_state(m.chat.id).mode == BotModes.QUICK,
                     content_types=["text"])
def quick_handler(message):
    chat_id = message.chat.id
    state = get_user_state(chat_id)
    consent = get_user_consent(chat_id)
    if not consent.privacy_accepted:
        show_privacy_consent(chat_id)
        return

    rag_context = get_rag_context(message.text)
    response = ask_yandex_gpt_with_context(
        question=message.text,
        context=rag_context,
        user_name=state.name
    )
    bot.send_message(chat_id, response)

# ========== ОБРАБОТКА ФАЙЛОВ ==========

@bot.message_handler(content_types=['document', 'photo'])
def handle_files(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "📁 Функция анализа планов будет доступна в следующем обновлении.")
    show_main_menu(chat_id)

# ========== ТЕСТОВЫЕ КОМАНДЫ ==========

@bot.message_handler(commands=['test_gpt'])
def test_gpt_handler(message):
    chat_id = message.chat.id
    test_response = call_yandex_gpt("Привет! Ответь коротко как дела?")
    bot.send_message(chat_id, f"Тест ЯндексGPT:\n{test_response}")

@bot.message_handler(commands=['test_rag'])
def test_rag_handler(message):
    chat_id = message.chat.id
    if kb:
        test_context = kb.get_rag_context("перепланировка квартиры")
        bot.send_message(chat_id, f"Тест RAG (первые 500 символов):\n{test_context[:500]}...")
    else:
        bot.send_message(chat_id, "RAG не инициализирован")

print("🤖 Бот «Пархоменко и компания» запущен...")
print(f"📁 База знаний: {KNOWLEDGE_DIR}")
print(f"📞 Группа для лидов: {LEADS_GROUP_CHAT_ID}")
print(f"🔑 ЯндексGPT FOLDER_ID: {FOLDER_ID}")

while True:
    try:
        bot.polling(non_stop=True, timeout=60)
    except Exception as e:
        print(f"❌ Ошибка polling: {e}")
        time.sleep(15)
