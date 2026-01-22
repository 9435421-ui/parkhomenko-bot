import os
import time
import datetime
import pytz
import requests
import telebot
from telebot import types
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
FOLDER_ID = os.getenv("FOLDER_ID")

LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "0"))
THREAD_ID_KVARTIRY = int(os.getenv("THREAD_ID_KVARTIRY", "0"))
THREAD_ID_KOMMERCIA = int(os.getenv("THREAD_ID_KOMMERCIA", "0"))
THREAD_ID_DOMA = int(os.getenv("THREAD_ID_DOMA", "0"))

# Content Agent Topics
THREAD_ID_DRAFTS = int(os.getenv("THREAD_ID_DRAFTS", "85"))
THREAD_ID_SEASONAL = int(os.getenv("THREAD_ID_SEASONAL", "87"))
THREAD_ID_LOGS = int(os.getenv("THREAD_ID_LOGS", "88"))

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Пути для файлов
UPLOAD_PLANS_DIR = os.getenv("UPLOAD_PLANS_DIR", "uploads_plans")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
KNOWLEDGE_DIR = "data/knowledge_base"
DB_PATH = "db/parkhomenko_bot.db"

os.makedirs(UPLOAD_PLANS_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(KNOWLEDGE_DIR, exist_ok=True)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN must be set in .env")
if not YANDEX_API_KEY or not FOLDER_ID:
    raise RuntimeError("YANDEX_API_KEY and FOLDER_ID must be set in .env")

bot = telebot.TeleBot(BOT_TOKEN)

# --------- CONTENT AGENT ---------
from content_agent import ContentAgent
from database import db
from auto_poster import run_auto_poster

# Подключение к базе данных будет выполнено в async контексте

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

        self.house_material = None  # Для домов
        self.commercial_purpose = None  # Для коммерции

        self.dialog_history = []
        self.has_plan = False
        self.plan_path = None
        self.change_plan = None
        self.voice_used = False
        self.preferred_time = None  # Для хранения удобного времени звонка
        self.source = None  # Источник трафика (из start параметра)


user_states: dict[int, UserState] = {}
user_consents: dict[int, UserConsent] = {}

# --------- Тексты ---------

PRIVACY_POLICY_TEXT = (
    "Здравствуйте! Я Антон, ИИ‑ассистент Юлии Пархоменко по перепланировкам и переоборудованию недвижимости.\n\n"
    "Перед тем как продолжить, подтвердите, пожалуйста:\n"
    "— согласие на обработку ваших персональных данных;\n"
    "— согласие на получение от нас сообщений и уведомлений.\n\n"
    "Нажимая кнопку ниже, вы даёте оба этих согласия."
)

AI_INTRO_TEXT = (
    "Я помогу собрать данные для консультации и подсказать, какие шаги по перепланировке и переоборудованию безопасны с точки зрения закона."
)

# --------- Утилиты ---------


def get_user_state(user_id: int) -> UserState:
    """Получить состояние пользователя (с загрузкой из БД если нужно)"""
    if user_id not in user_states:
        import asyncio
        try:
            state_dict, _ = asyncio.run(db.load_user_state(user_id))
            if state_dict:
                state = UserState()
                for key, value in state_dict.items():
                    if hasattr(state, key):
                        setattr(state, key, value)
                user_states[user_id] = state
                print(f"✅ Состояние user {user_id} восстановлено из БД")
            else:
                user_states[user_id] = UserState()
        except Exception as e:
            print(f"⚠️ Ошибка загрузки состояния user {user_id}: {e}")
            user_states[user_id] = UserState()

    return user_states[user_id]


def get_user_consent(user_id: int) -> UserConsent:
    """Получить согласия пользователя (с загрузкой из БД если нужно)"""
    if user_id not in user_consents:
        import asyncio
        try:
            _, consent_dict = asyncio.run(db.load_user_state(user_id))
            if consent_dict:
                consent = UserConsent()
                for key, value in consent_dict.items():
                    if hasattr(consent, key):
                        setattr(consent, key, value)
                user_consents[user_id] = consent
                print(f"✅ Согласия user {user_id} восстановлены из БД")
            else:
                user_consents[user_id] = UserConsent()
        except Exception as e:
            print(f"⚠️ Ошибка загрузки согласий user {user_id}: {e}")
            user_consents[user_id] = UserConsent()

    return user_consents[user_id]


def save_user_state_to_db(user_id: int):
    """Сохранить текущее состояние пользователя в БД"""
    import asyncio
    try:
        state = user_states.get(user_id)
        consent = user_consents.get(user_id)

        if state:
            state_dict = {k: v for k, v in state.__dict__.items()}
            consent_dict = {k: v for k, v in consent.__dict__.items()} if consent else None

            asyncio.run(db.save_user_state(user_id, state_dict, consent_dict))
            print(f"💾 Состояние user {user_id} сохранено в БД")
    except Exception as e:
        print(f"⚠️ Ошибка сохранения состояния user {user_id}: {e}")


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
    markup.add(
        types.InlineKeyboardButton("📝 Оставить заявку", callback_data="mode_quiz")
    )
    bot.send_message(chat_id, "Чем бот может вам помочь?", reply_markup=markup)


# --------- Лиды ---------


def save_lead_and_notify(user_id: int):
    state = get_user_state(user_id)

    # Сохраняем в базу данных
    try:
        import asyncio
        asyncio.run(db.save_lead(
            name=state.name,
            phone=state.phone,
            extra_contact=state.extra_contact,
            object_type=state.object_type,
            city=state.city,
            change_plan=state.change_plan,
            bti_status=state.bti_status,
            house_material=state.house_material,
            commercial_purpose=state.commercial_purpose,
            source=state.source
        ))
        print(f"✅ Лид сохранен в БД: {state.name}, {state.phone}, источник: {state.source or 'не указан'}")
    except Exception as e:
        print(f"❌ Ошибка сохранения лида в БД: {e}")

    lead_info = f"""
📋 Новая заявка на перепланировку

👤 Имя: {state.name}
📞 Телефон (TG): {state.phone}
📪 Доп. контакт: {state.extra_contact or 'не указан'}
🏠 Тип объекта: {state.object_type or 'не выбран'}
🏙️ Город: {state.city or 'не указан'}
🛠️ Что хочет изменить: {state.change_plan or 'не указано'}
📄 Статус БТИ: {state.bti_status or 'не указан'}
🔗 Источник: {state.source or 'не указан'}
    """.strip()

    # Добавляем специфические поля для домов и коммерции
    if state.object_type == "Дом" and state.house_material:
        lead_info += f"\n🏗️ Материал дома: {state.house_material}"
    elif state.object_type == "Коммерция" and state.commercial_purpose:
        lead_info += f"\n🏢 Назначение помещения: {state.commercial_purpose}"

    if state.preferred_time:
        lead_info += f"\n🕐 Удобное время звонка: {state.preferred_time}"

    lead_info += f"\n🕐 Время заявки: {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}\n👤 User ID: {user_id}"

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
            bot.send_message(
                LEADS_GROUP_CHAT_ID, lead_info, message_thread_id=thread_id
            )
        else:
            bot.send_message(LEADS_GROUP_CHAT_ID, lead_info)
        print(f"✅ Лид отправлен в группу: {state.name}, {state.phone}")
    except Exception as e:
        print(f"❌ Ошибка отправки лида: {e}")
        try:
            bot.send_message(ADMIN_ID, f"❌ Ошибка отправки лида: {e}\n\n{lead_info}")
        except:
            pass

    # Финальные сообщения с учётом времени по Москве
    moscow_tz = pytz.timezone('Europe/Moscow')
    now_moscow = datetime.datetime.now(moscow_tz)
    current_hour = now_moscow.hour

    if 9 <= current_hour < 20:
        # Рабочее время
        bot.send_message(
            user_id,
            "Спасибо, вы ответили на основные вопросы. Мы сохранили данные по вашей квартире и перепланировке, это поможет специалисту подготовиться к разговору.\n\n"
            "Наша компания работает с 09:00 до 20:00 по Московскому времени. Специалист команды Юлии Пархоменко свяжется с вами в ближайшее время, чтобы оценить риски по перепланировке и обсудить дальнейшие шаги."
        )
    else:
        # Нерабочее время
        state.mode = "waiting_time"
        bot.send_message(
            user_id,
            "Спасибо, вы ответили на основные вопросы. Мы сохранили данные по вашей квартире и перепланировке, это поможет специалисту подготовиться к разговору.\n\n"
            "Сейчас наша команда отдыхает. Мы свяжемся с вами завтра после 09:00 по Московскому времени. Подскажите, в какое время вам будет удобнее принять звонок или сообщение?"
        )

    # Общее финальное сообщение
    bot.send_message(
        user_id,
        "Вы заполнили основную информацию, этого достаточно, чтобы специалист подготовился к разговору.\n\n"
        "Вы можете оставить дополнительную информацию в этом чате:\n"
        "- задать вопросы в свободной форме;\n"
        "- отправить фотографии и документы по квартире и перепланировке;\n"
        "- записать голосовое сообщение с пояснениями.\n\n"
        "Всё, что вы сюда отправите, увидит специалист перед тем, как связаться с вами."
    )


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
    client_messages = [h["text"] for h in state.dialog_history if h["role"] == "user"]

    # Формируем полный текст диалога для анализа
    full_dialog = "\n".join(
        [
            f"{'Клиент' if h['role'] == 'user' else 'Антон'}: {h['text']}"
            for h in state.dialog_history
        ]
    )

    # Запрашиваем у YandexGPT анализ диалога
    analysis_prompt = f"""
Проанализируй диалог с клиентом и выдели:
1. Основной запрос клиента (кратко, 1-2 предложения)
2. Выявленные потребности (список из 3-5 пунктов)
3. Важные детали для менеджера (что нужно уточнить, на что обратить внимание)

Учитывай информацию из state, которая уже есть:
- Город: {state.city or 'не указан'}
- Тип дома: {state.object_type or 'не указан'}
- Документы БТИ: {state.bti_status or 'не указан'}

НЕ предлагай уточнять то, что клиент уже сказал!
Если клиент уже рассказал про город, тип дома, документы — НЕ пиши "уточнить город" и т.п.
Упрощай язык: вместо "уточнить планы по замене коммуникаций" пиши "уточнить, планирует ли клиент переносить кухню/мокрые зоны или менять расположение сантехники".

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


def call_yandex_gpt(
    prompt: str, user_name: str = None, model: str = "yandexgpt"
) -> str:
    try:
        headers = {
            "Authorization": f"Api-Key {YANDEX_API_KEY}",
            "Content-Type": "application/json",
        }

        greeting = f"{user_name}, " if user_name else ""

        data = {
            "modelUri": f"gpt://{FOLDER_ID}/{model}/latest",
            "completionOptions": {
                "stream": False,
                "temperature": 0.2,
                "maxTokens": 400,
            },
            "messages": [
                {
                    "role": "system",
                    "text": (
                        "Ты - Антон, специалист по перепланировкам в компании «Пархоменко и компания». "
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
                    ),
                },
                {"role": "user", "text": prompt},
            ],
        }

        response = requests.post(
            "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
            headers=headers,
            json=data,
            timeout=60,
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


def ask_yandex_gpt_with_context(
    question: str, context: str = "", user_name: str = None
) -> str:
    prompt = f"""
Контекст из базы знаний:
{context}

Вопрос: {question}

Дай короткий конкретный ответ (2-3 абзаца) и задай уточняющий вопрос для продолжения диалога.
"""
    return call_yandex_gpt(prompt, user_name=user_name)


# --------- Yandex SpeechKit (Voice Transcription) ---------


def transcribe_audio(file_path: str) -> str:
    try:
        with open(file_path, 'rb') as f:
            audio_data = f.read()

        headers = {
            'Authorization': f'Api-Key {YANDEX_API_KEY}',
        }

        if file_path.endswith('.ogg'):
            content_type = 'audio/ogg;codecs=opus'
        elif file_path.endswith('.mp3'):
            content_type = 'audio/mpeg'
        else:
            content_type = 'audio/mpeg'

        headers['Content-Type'] = content_type

        params = {
            'lang': 'ru-RU',
            'folderId': FOLDER_ID
        }

        url = 'https://stt.api.cloud.yandex.net/speech/v1/stt:recognize'

        response = requests.post(url, headers=headers, params=params, data=audio_data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            return result.get('result', '')
        else:
            print(f"STT API error: {response.status_code} - {response.text}")
            return ''

    except Exception as e:
        print(f"Error in transcribe_audio: {e}")
        return ''


# --------- Хэндлеры согласий ---------


@bot.message_handler(commands=["start"])
def start_handler(message):
    user_id = message.chat.id
    state = get_user_state(user_id)
    consent = get_user_consent(user_id)

    # Extract start parameter from deep link
    start_param = 'organic'  # Значение по умолчанию для органического трафика
    if len(message.text.split()) > 1:
        # Format: /start <parameter>
        param_text = message.text.split()[1].strip()
        if param_text:  # Проверяем, что параметр не пустой
            start_param = param_text

    state.source = start_param
    save_user_state_to_db(user_id)
    print(f"📊 User {user_id} came from source: {start_param}")

    if not consent.privacy_accepted:
        show_privacy_consent(user_id)
        return

    if not consent.ai_disclaimer_seen:
        show_ai_disclaimer(user_id)
        consent.ai_disclaimer_seen = True
        consent.consent_timestamp = datetime.datetime.now()

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(
            types.KeyboardButton("📱 Поделиться контактом", request_contact=True)
        )
        bot.send_message(
            user_id,
            "Для продолжения работы поделитесь своим контактом Telegram — это защитит нас от спама и поможет быстрее связаться.",
            reply_markup=markup,
        )
        return

    if not consent.contact_received:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(
            types.KeyboardButton("📱 Поделиться контактом", request_contact=True)
        )
        bot.send_message(
            user_id,
            "Для продолжения работы поделитесь своим контактом Telegram.",
            reply_markup=markup,
        )
        return

    show_main_menu(user_id)


@bot.message_handler(commands=["privacy"])
def privacy_info(message):
    show_privacy_consent(message.chat.id)


@bot.message_handler(
    func=lambda m: m.text in ["✅ Я согласен и хочу продолжить", "❌ Отказаться"]
)
def privacy_consent_handler(message):
    user_id = message.chat.id
    consent = get_user_consent(user_id)

    if "Отказаться" in message.text:
        bot.send_message(
            user_id, "Без согласия на обработку данных использовать бота нельзя."
        )
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
        reply_markup=markup,
    )


@bot.message_handler(
    content_types=["contact"],
    func=lambda m: get_user_consent(m.chat.id).privacy_accepted
    and not get_user_consent(m.chat.id).contact_received,
)
def initial_contact_handler(message):
    user_id = message.chat.id
    state = get_user_state(user_id)
    consent = get_user_consent(user_id)

    # Валидация номера телефона
    phone = message.contact.phone_number
    clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')

    if not clean_phone.isdigit() or len(clean_phone) not in [10, 11, 12]:
        bot.send_message(
            user_id,
            "⚠️ Номер телефона некорректен. Используйте кнопку «Поделиться контактом»."
        )
        return

    state.phone = phone
    save_user_state_to_db(user_id)
    consent.contact_received = True

    # МИНИМАЛЬНЫЙ ЛИД после получения контакта
    contact_lead = f"""
🆕 НОВЫЙ КОНТАКТ: {message.contact.first_name} {message.contact.last_name or ''}
📞 Телефон: {state.phone}
👤 User ID: {user_id}
🕐 Время: {datetime.datetime.now().strftime("%d.%m.%Y %H:%M")}
ℹ️ Статус: контакт получен, тип объекта и заявка ещё не оформлены
    """.strip()

    try:
        bot.send_message(LEADS_GROUP_CHAT_ID, contact_lead)
        print(
            f"✅ Минимальный лид отправлен: {message.contact.first_name}, {state.phone}"
        )
    except Exception as e:
        print(f"❌ Ошибка отправки минимального лида: {e}")

    # Извлекаем имя из контакта
    contact_name = message.contact.first_name or ""

    hide_kb = types.ReplyKeyboardRemove()

    if contact_name:
        # Если имя есть — предлагаем подтвердить
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                f"✅ Да, {contact_name}", callback_data=f"confirm_name_{contact_name}"
            )
        )
        markup.add(
            types.InlineKeyboardButton(
                "✏️ Нет, указать другое", callback_data="change_name"
            )
        )

        bot.send_message(
            user_id,
            f"Спасибо! Ваш контакт {state.phone} сохранён.\n\n"
            f"Могу к вам обращаться «{contact_name}»?",
            reply_markup=markup,
        )
    else:
        # Если имени нет — спрашиваем
        bot.send_message(
            user_id,
            f"Спасибо! Ваш контакт {state.phone} сохранён.\n\nКак к вам обращаться?",
            reply_markup=hide_kb,
        )


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("confirm_name_")
    or call.data == "change_name"
)
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
            message_id=call.message.message_id,
        )
        show_main_menu(user_id)

    elif call.data == "change_name":
        # Запрос нового имени
        bot.edit_message_text(
            "Хорошо, напишите, как к вам обращаться:",
            chat_id=user_id,
            message_id=call.message.message_id,
        )


@bot.message_handler(
    func=lambda m: get_user_consent(m.chat.id).contact_received
    and get_user_state(m.chat.id).name is None
    and get_user_state(m.chat.id).mode is None,
    content_types=["text"],
)
def initial_name_handler(message):
    user_id = message.chat.id
    state = get_user_state(user_id)

    state.name = message.text.strip()
    bot.send_message(user_id, f"Приятно познакомиться, {state.name}!")
    show_main_menu(user_id)


@bot.message_handler(
    func=lambda m: get_user_state(m.chat.id).mode == "waiting_time",
    content_types=["text"],
)
def time_handler(message):
    from datetime import datetime

    chat_id = message.chat.id
    state = get_user_state(chat_id)
    preferred_time = message.text.strip()

    # Сохраняем preferred_time
    state.preferred_time = preferred_time
    save_user_state_to_db(chat_id)

    # Определяем текущий день и время
    now = datetime.now()
    is_weekend = now.weekday() >= 5  # 5=суббота, 6=воскресенье
    is_saturday = now.weekday() == 5
    is_evening = now.hour >= 18 or now.hour < 9
    is_saturday_late = is_saturday and now.hour >= 16

    # Отправляем в группу лидов
    lead_update = f"""
📞 Уточнение времени звонка

👤 {state.name} ({state.phone})
🕐 Запрос клиента: {preferred_time}
    """.strip()

    try:
        bot.send_message(LEADS_GROUP_CHAT_ID, lead_update)
    except Exception as e:
        print(f"❌ Ошибка отправки времени: {e}")

    # Отправляем клиенту
    bot.send_message(
        chat_id,
        f"Спасибо, {state.name}!\n\n"
        f"📞 Вы указали: {preferred_time}\n"
        f"👨‍💼 Наш специалист постарается позвонить в это время.\n\n"
        f"📅 Мы работаем ежедневно с 10:00 до 20:00 по Москве.",
    )

    state.mode = None
    # НЕ показываем меню после завершения


# ========== CALLBACK HANDLER: Выбор режимов и объектов ==========


@bot.callback_query_handler(
    func=lambda call: call.data.startswith("mode_") or call.data.startswith("obj_")
)
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
        state.quiz_step = 2  # По умолчанию начинаем с шага 2

        # Извлекаем данные из истории диалога если есть
        if state.dialog_history:
            # Извлекаем город
            for msg in state.dialog_history:
                text_lower = msg.get("text", "").lower()
                if "москв" in text_lower:
                    state.city = "Москва"
                    state.quiz_step = 5  # Пропускаем шаг города
                elif "химк" in text_lower:
                    state.city = "Химки"
                    state.quiz_step = 5
                elif "сочи" in text_lower:
                    state.city = "Сочи"
                    state.quiz_step = 5
                elif any(
                    city in text_lower
                    for city in ["краснодар", "петербург", "екатеринбург"]
                ):
                    state.city = msg.get("text", "").strip()
                    state.quiz_step = 5

            # Извлекаем этаж (формат 2/5, 16/25 и т.п.)
            for msg in state.dialog_history:
                text = msg.get("text", "")
                if "/" in text and len(text.split("/")) == 2:
                    parts = text.split("/")
                    if parts[0].strip().isdigit() and parts[1].strip().isdigit():
                        state.floor = parts[0].strip()
                        state.total_floors = parts[1].strip()
                        if state.quiz_step == 5:
                            state.quiz_step = 6  # Пропускаем этаж

            # Извлекаем описание работ
            for msg in state.dialog_history:
                text_lower = msg.get("text", "").lower()
                if any(
                    word in text_lower
                    for word in [
                        "объединить",
                        "перенести",
                        "расширить",
                        "убрать",
                        "снести",
                        "увеличить",
                    ]
                ):
                    state.change_plan = msg.get("text", "")
                    if state.quiz_step == 6:
                        state.quiz_step = 7  # Пропускаем описание
                    break

        # Отправляем соответствующий вопрос в зависимости от шага
        if state.quiz_step == 2:
            # Пропускаем шаг дополнительного контакта, сразу переходим к выбору типа объекта
            state.quiz_step = 3
            markup = types.InlineKeyboardMarkup()
            markup.row(
                types.InlineKeyboardButton("Квартира", callback_data="obj_kvartira"),
                types.InlineKeyboardButton("Дом", callback_data="obj_dom")
            )
            markup.row(
                types.InlineKeyboardButton("Нежилое помещение (офис, магазин и т.п.)", callback_data="obj_kommertsia")
            )

            bot.send_message(user_id, "Выберите тип объекта:\n- квартира\n- дом\n- нежилое помещение (офис, магазин и т.п.).", reply_markup=markup)
        elif state.quiz_step == 5:
            bot.send_message(
                user_id, "Укажите этаж и этажность дома (например: 5/9 или просто 5):"
            )
        elif state.quiz_step == 6:
            bot.send_message(
                user_id,
                "Перепланировка уже выполнена или только планируете? Напишите 'выполнена' или 'планируется'.",
            )
        elif state.quiz_step == 7:
            bot.send_message(
                user_id,
                "Кратко опишите, что хотите изменить в перепланировке (объединить комнаты, перенести санузел, расширить кухню и т.п.).",
            )
        else:
            # Если пропустили всё - переходим к БТИ
            bot.send_message(
                user_id,
                "Если у вас есть дополнительный способ связи (WhatsApp/почта/другой номер) — напишите его, или отправьте «нет».",
            )

    elif call.data == "mode_dialog":
        state.mode = BotModes.DIALOG
        bot.send_message(
            user_id, f"{state.name}, опишите вашу ситуацию по перепланировке."
        )

    elif call.data == "mode_quick":
        state.mode = BotModes.QUICK
        bot.send_message(user_id, f"{state.name}, напишите свой вопрос.")

    # Выбор типа объекта в квизе
    elif call.data.startswith("obj_") and state.mode == BotModes.QUIZ:
        if call.data == "obj_kvartira":
            state.object_type = "Квартира"
            state.quiz_step = 4  # Пропускаем специфические вопросы для домов/коммерции
            bot.send_message(user_id, "Укажите город/регион:")
        elif call.data == "obj_kommertsia":
            state.object_type = "Коммерция"
            # Добавляем шаг для назначения помещения
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🍽️ Общепит", callback_data="purpose_общепит"))
            markup.add(types.InlineKeyboardButton("🛍️ Торговля", callback_data="purpose_торговля"))
            markup.add(types.InlineKeyboardButton("💼 Офис", callback_data="purpose_офис"))
            markup.add(types.InlineKeyboardButton("🏥 Медицина", callback_data="purpose_медицина"))
            markup.add(types.InlineKeyboardButton("✏️ Другое", callback_data="purpose_другое"))
            state.quiz_step = 3.5
            bot.send_message(user_id, "Укажите назначение помещения:", reply_markup=markup)
        elif call.data == "obj_dom":
            state.object_type = "Дом"
            # Добавляем шаг для материала дома
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("🧱 Кирпич", callback_data="material_кирпич"))
            markup.add(types.InlineKeyboardButton("🪵 Брус", callback_data="material_брус"))
            markup.add(types.InlineKeyboardButton("🏗️ Каркас", callback_data="material_каркас"))
            markup.add(types.InlineKeyboardButton("🧱 Пеноблок", callback_data="material_пеноблок"))
            markup.add(types.InlineKeyboardButton("✏️ Другое", callback_data="material_другое"))
            state.quiz_step = 3.5
            bot.send_message(user_id, "Укажите материал дома:", reply_markup=markup)
        else:
            state.object_type = "Неизвестно"
            state.quiz_step = 4
            bot.send_message(user_id, "Укажите город/регион:")

    # Выбор материала дома
    elif call.data.startswith("material_") and state.mode == BotModes.QUIZ:
        material = call.data.replace("material_", "")
        state.house_material = material
        state.quiz_step = 4  # Переходим к следующему шагу
        bot.send_message(user_id, "Укажите город/регион:")

    # Выбор назначения коммерческого помещения
    elif call.data.startswith("purpose_") and state.mode == BotModes.QUIZ:
        purpose = call.data.replace("purpose_", "")
        state.commercial_purpose = purpose
        state.quiz_step = 4  # Переходим к следующему шагу
        bot.send_message(user_id, "Укажите город/регион:")


# ========== КВИЗ: Сбор заявки ==========


@bot.message_handler(
    func=lambda m: get_user_state(m.chat.id).mode == BotModes.QUIZ,
    content_types=["text"],
)
def quiz_handler(message):
    chat_id = message.chat.id
    state = get_user_state(chat_id)

    # Шаг 2: пропускаем, сразу к шагу 3 (выбор типа объекта)

    # Шаг 4: город/регион (после выбора объекта через callback)
    if state.quiz_step == 4:
        state.city = message.text.strip()
        save_user_state_to_db(chat_id)
        state.quiz_step = 5
        bot.send_message(
            chat_id, "Укажите город или регион, где находится объект."
        )
        return

    # Шаг 5: этаж/этажность дома
    if state.quiz_step == 5:
        parts = message.text.strip().split("/")
        if len(parts) >= 2:
            state.floor = parts[0].strip()
            state.total_floors = parts[1].strip()
        else:
            state.floor = message.text.strip()
            state.total_floors = None

        save_user_state_to_db(chat_id)

        # Дополнительные вопросы в зависимости от типа объекта
        if state.object_type == "Дом" and not state.house_material:
            state.quiz_step = 5.1
            bot.send_message(
                chat_id,
                "Укажите материал дома (кирпич, дерево, пеноблок и т.п.) или напишите 'другое' для уточнения:"
            )
        elif state.object_type == "Коммерция" and not state.commercial_purpose:
            state.quiz_step = 5.1
            bot.send_message(
                chat_id,
                "Укажите назначение помещения (офис, магазин, склад, производство и т.п.):"
            )
        else:
            state.quiz_step = 6
            bot.send_message(
                chat_id,
                "Перепланировка уже выполнена или только планируете? Напишите 'выполнена' или 'планируется'.",
            )
        return

    # Шаг 5.1: материал дома или назначение коммерции
    if state.quiz_step == 5.1:
        if state.object_type == "Дом":
            state.house_material = message.text.strip()
        elif state.object_type == "Коммерция":
            state.commercial_purpose = message.text.strip()

        save_user_state_to_db(chat_id)
        state.quiz_step = 6
        bot.send_message(
            chat_id,
            "Перепланировка уже выполнена или только планируете? Напишите 'выполнена' или 'планируется'.",
        )
        return

    # Шаг 6: статус перепланировки
    if state.quiz_step == 6:
        # Нормализуем ответ
        text_lower = message.text.strip().lower()
        if text_lower in ['выполнена', 'выполнено', 'уже выполнена', 'уже выполнено']:
            state.remodeling_status = 'выполнена'
        elif text_lower in ['планируется', 'планирую', 'будет выполнена', 'будет выполнено']:
            state.remodeling_status = 'планируется'
        else:
            state.remodeling_status = text_lower  # Сохраняем как есть для неизвестных ответов

        save_user_state_to_db(chat_id)
        state.quiz_step = 7
        bot.send_message(
            chat_id,
            "Кратко опишите, что хотите изменить в перепланировке (объединить комнаты, перенести санузел, расширить кухню и т.п.).",
        )
        return

    # Шаг 7: описание изменений
    if state.quiz_step == 7:
        state.change_plan = message.text.strip()
        save_user_state_to_db(chat_id)
        state.quiz_step = 8
        bot.send_message(
            chat_id,
            "Есть ли у вас сейчас документы БТИ (поэтажный план, экспликация, техпаспорт)? Напишите: есть/нет и какие именно.",
        )
        return

    # Шаг 8: статус документов БТИ + завершение квиза
    if state.quiz_step == 8:
        state.bti_status = message.text.strip()
        save_user_state_to_db(chat_id)
        # Завершение квиза - сохраняем лид и отправляем финальные сообщения
        save_lead_and_notify(chat_id)
        # Сброс состояния
        state.mode = None
        state.quiz_step = 0
        return

    # Шаг 11: полезность базы знаний
    if state.quiz_step == 11:
        state.knowledge_helpful = message.text.strip()
        state.quiz_step = 12
        bot.send_message(
            chat_id,
            "Как быстро бот отвечал на ваши вопросы? (мгновенно/быстро/нормально/медленно)"
        )
        return

    # Шаг 12: скорость ответа
    if state.quiz_step == 12:
        state.response_speed = message.text.strip()
        state.quiz_step = 13
        bot.send_message(
            chat_id,
            "Будете ли вы рекомендовать этого бота друзьям? (да/нет/возможно)"
        )
        return

    # Шаг 13: рекомендация друзьям
    if state.quiz_step == 13:
        state.recommendation = message.text.strip()
        state.quiz_step = 14
        bot.send_message(
            chat_id,
            "Есть ли пожелания по улучшению бота? (напишите кратко или 'нет')"
        )
        return

    # Шаг 14: пожелания по улучшению + завершение квиза
    if state.quiz_step == 14:
        state.improvement_suggestions = message.text.strip()
        save_lead_and_notify(chat_id)
        bot.send_message(
            chat_id,
            f"✅ Спасибо, {state.name}! Ваша заявка принята.\n\n"
            f"Команда «Пархоменко и компания» свяжется с вами по номеру {state.phone} "
            f"ежедневно с 10:00 до 20:00 по Москве для обсуждения деталей и предварительного расчёта.\n\n"
            f"Спасибо за обратную связь по работе бота!",
        )
        # Сброс состояния БЕЗ показа меню
        state.mode = None
        state.quiz_step = 0
        return


# ========== ДИАЛОГОВЫЙ РЕЖИМ ==========


@bot.message_handler(
    func=lambda m: get_user_state(m.chat.id).mode == BotModes.DIALOG,
    content_types=["text"],
)
def dialog_handler(message):
    chat_id = message.chat.id
    state = get_user_state(chat_id)
    consent = get_user_consent(chat_id)
    if not consent.privacy_accepted:
        show_privacy_consent(chat_id)
        return

    # Распознавание frustration - клиент раздражён
    frustration_words = [
        "шоке",
        "кругу",
        "переспрашиваете",
        "раздражает",
        "повторяете",
        "не понимаете",
        "не слушаете",
        "уже говорил",
        "уже писал",
        "забываете",
    ]
    if any(word in message.text.lower() for word in frustration_words):
        # НЕ сохранять это сообщение в историю как полезное!
        # Не передавать в change_plan!

        summary = f"Извините за неудобство, {state.name}! Давайте я помогу вам прямо здесь.\n\n"

        if state.city:
            summary += f"📍 Город: {state.city}\n"
        if state.floor:
            summary += f"🏢 Этаж: {state.floor}/{state.total_floors}\n"

        # Ищем последний НОРМАЛЬНЫЙ запрос (не frustration)
        last_normal = None
        for msg in reversed(state.dialog_history):
            text_lower = msg.get("text", "").lower()
            if not any(fw in text_lower for fw in frustration_words):
                if any(
                    word in text_lower
                    for word in ["объединить", "убрать", "перенести", "расширить"]
                ):
                    last_normal = msg.get("text")
                    break

        if last_normal:
            summary += f"📝 Планируете: {last_normal}\n"

        summary += "\n🤝 Наш специалист может приехать на осмотр, сделать замеры и подготовить проект. Хотите обсудить детали здесь или соединить со специалистом?"

        bot.send_message(chat_id, summary)
        return

    # Удален дублированный код frustration recognition

    # Проверка на запрос связи с человеком
    trigger_words = [
        "соедините",
        "специалист",
        "менеджер",
        "человек",
        "живой",
        "реальный",
        "заказать",
        "связаться",
    ]
    if any(word in message.text.lower() for word in trigger_words):
        # Создаём лид НЕМЕДЛЕННО при запросе специалиста
        save_lead_and_notify(chat_id)

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
            f"📞 Специалисты работают ежедневно с 10:00 до 20:00 по Москве.\n\n"
            "Укажите, пожалуйста, в какое время вам удобно принять звонок?",
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
        history_text = "\n".join(
            [
                f"{'Клиент' if h['role'] == 'user' else 'Антон'}: {h['text']}"
                for h in recent_history
            ]
        )

    system_prompt = """
Ты — Антон, специалист по перепланировкам «Пархоменко и компания» (Москва/МО, согласование перепланировок под ключ, 10+ лет).

ЖЕЛЕЗНЫЕ ПРАВИЛА:
1. Читай историю — НЕ задавай вопросы, на которые клиент УЖЕ ответил
2. НЕ повторяй информацию, которую УЖЕ озвучил
3. Каждый ответ — ТОЛЬКО новая информация
4. Лимит: 250-350 символов (2-3 предложения max)
5. УПОМИНАЙ КОМПАНИЮ: в каждом 2-3 ответе
6. НЕ ПРЕДПОЛАГАЙ ГОРОД: НЕ говори "в Москве" пока клиент не назвал город
7. КОГДА КЛИЕНТ ХОЧЕТ ОБСУДИТЬ ДЕТАЛИ:
   - Задай 2-3 конкретных вопроса про объект (тип дома, документы БТИ, коммуникации)
   - Дай 2-3 совета из базы знаний
   - Только ПОТОМ мягко предложи заявку
8. СТОИМОСТЬ:
   - НИКОГДА не называй конкретные суммы.
   - Если клиент спрашивает про цену, стоимость, тариф или «по деньгам» — объясни, что цена зависит от объекта, объёма работ и документов.
   - Предложи обсудить стоимость со специалистом и обязательно скажи, что подберёте комфортные условия по оплате под ситуацию клиента.
9. ВОПРОСЫ НА ЧЕЛОВЕЧЕСКОМ ЯЗЫКЕ:
   - Задавай вопросы простым языком, как будто разговариваешь с человеком
   - Не используй технические термины без объяснения
   - Не задавай сразу много вопросов — максимум 2-3 в одном ответе
   - Спрашивай по порядку: город, этаж, тип дома, есть ли выписка из ЕГРН или план БТИ.
   - Если у клиента нет плана или документов под рукой — скажи, что это нормально, и попроси описать квартиру словами (где сейчас ванная/кухня и как он хочет её изменить).
   - Не пытайся угадывать ответы — всегда спрашивай явно, простым языком.

ПРИМЕРЫ ПРАВИЛЬНЫХ ДИАЛОГОВ:

1) Клиент: "хочу объединить ванную"
   Ты: "Объединение санузла требует согласования. Важно не трогать несущие стены и гидроизоляция пола. В каком городе квартира? На каком этаже?"

2) Клиент: "Сочи, 2/5"
   Ты: "В Сочи процесс аналогичен. На 2 этаже нельзя расширять мокрую зону над жилыми комнатами первого. Это панель, монолит или кирпич?"

3) Клиент: "панель"
   Ты: "В панельке перегородка обычно не несущая, сносить можно. Планируете менять разводку труб или стояки? Есть документы БТИ?"

4) Клиент: "хочу обсудить детали"
   Ты: "Хорошо! Уточните: какой тип дома? Есть документы БТИ? Планируете менять коммуникации? Для Сочи важно учитывать нормы Краснодарского края."



7) Клиент: "соедините со специалистом"
   Ты: "Соединяю. Когда вам удобно принять звонок?"

8) Клиент: "Хочу увеличить ванную за счёт коридора"
   Ты: "Увеличение ванной за счёт коридора — перепланировка, которую нужно согласовывать. Важно понять, где находится ванная и что под и над вашей квартирой. В каком городе квартира, на каком этаже и сколько этажей в доме? Дом панельный, монолитный или кирпичный? Есть у вас выписка из ЕГРН или план БТИ, или проще рассказать на словах, как сейчас устроена квартира?"

НЕ ДЕЛАЙ НИКОГДА:
× Не повторяй уже сказанное
× НЕ называй конкретные цены и суммы, даже если клиент спрашивает. Объясняй, что стоимость рассчитывается индивидуально, и перенаправляй обсуждение стоимости к специалисту, обещая комфортные условия по оплате.
× НЕ говори "в Москве" пока клиент не назвал город
× НЕ предлагай заявку сразу — сначала задай вопросы и дай советы
× Не уходи от обсуждения к продаже
× Не спрашивай про "статус коридора/помещения" — лучше спроси "есть ли у вас план БТИ или техпаспорт"
""".strip()

    full_prompt = f"""
{system_prompt}

================ КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ ================
{rag_context}

{f"ИСТОРИЯ ДИАЛОГА (ЧТО УЖЕ БЫЛО СКАЗАНО):\n{history_text}\n" if history_text else ""}

НОВЫЙ ВОПРОС КЛИЕНТА:
{message.text}

ТВОЯ ЗАДАЧА:
1. Прочитай ИСТОРИЮ — что клиент УЖЕ сказал (город, этаж, тип дома)
2. НЕ повторяй информацию, которую УЖЕ давал
3. Дай ТОЛЬКО новую полезную информацию из КОНТЕКСТА (250-350 символов)
4. Если клиент раздражён/требует специалиста — сразу переходи к контакту
5. Каждое сообщение должно ПРОДВИГАТЬ диалог вперёд, а не повторять предыдущее
"""

    response = call_yandex_gpt(full_prompt, user_name=state.name)

    state.dialog_history.append({"role": "assistant", "text": response})
    bot.send_message(chat_id, response)

    # УБРАНА автоматическая отправка заявки после 3 сообщений
    # Теперь квиз запускается ТОЛЬКО по кнопке "📝 Оставить заявку" или явной просьбе клиента


# ========== БЫСТРАЯ КОНСУЛЬТАЦИЯ ==========


def build_system_prompt():
    """Общий system_prompt для dialog_handler и quick_handler"""
    return """
Ты — Антон, специалист по перепланировкам «Пархоменко и компания» (Москва/МО, согласование перепланировок под ключ, 10+ лет).

ЖЕЛЕЗНЫЕ ПРАВИЛА:
1. Читай историю — НЕ задавай вопросы, на которые клиент УЖЕ ответил
2. НЕ повторяй информацию, которую УЖЕ озвучил
3. Каждый ответ — ТОЛЬКО новая информация
4. Лимит: 250-350 символов (2-3 предложения max)
5. УПОМИНАЙ КОМПАНИЮ: в каждом 2-3 ответе
6. НЕ ПРЕДПОЛАГАЙ ГОРОД: НЕ говори "в Москве" пока клиент не назвал город
7. КОГДА КЛИЕНТ ХОЧЕТ ОБСУДИТЬ ДЕТАЛИ:
   - Задай 2-3 конкретных вопроса про объект (тип дома, документы БТИ, коммуникации)
   - Дай 2-3 совета из базы знаний
   - Только ПОТОМ мягко предложи заявку
8. СТОИМОСТЬ:
   - НИКОГДА не называй конкретные суммы.
   - Если клиент спрашивает про цену, стоимость, тариф или «по деньгам» — объясни, что цена зависит от объекта, объёма работ и документов.
   - Предложи обсудить стоимость со специалистом и обязательно скажи, что подберёте комфортные условия по оплате под ситуацию клиента.

ПРИМЕРЫ ПРАВИЛЬНЫХ ДИАЛОГОВ:

1) Клиент: "хочу объединить ванную"
   Ты: "Объединение санузла требует согласования. Важно не трогать несущие стены и гидроизоляция пола. В каком городе квартира? На каком этаже?"

2) Клиент: "Сочи, 2/5"
   Ты: "В Сочи процесс аналогичен. На 2 этаже нельзя расширять мокрую зону над жилыми комнатами первого. Это панель, монолит или кирпич?"

3) Клиент: "панель"
   Ты: "В панельке перегородка обычно не несущая, сносить можно. Планируете менять разводку труб или стояки? Есть документы БТИ?"

4) Клиент: "хочу обсудить детали"
   Ты: "Хорошо! Уточните: какой тип дома? Есть документы БТИ? Планируете менять коммуникации? Для Сочи важно учитывать нормы Краснодарского края."



7) Клиент: "соедините со специалистом"
   Ты: "Соединяю. Когда вам удобно принять звонок?"

НЕ ДЕЛАЙ НИКОГДА:
× Не повторяй уже сказанное
× НЕ называй конкретные цены и суммы, даже если клиент спрашивает. Объясняй, что стоимость рассчитывается индивидуально, и перенаправляй обсуждение стоимости к специалисту, обещая комфортные условия по оплате.
× НЕ говори "в Москве" пока клиент не назвал город
× НЕ предлагай заявку сразу — сначала задай вопросы и дай советы
× Не уходи от обсуждения к продаже
""".strip()


def build_history_text(state):
    """Общая функция для формирования истории диалога"""
    if len(state.dialog_history) <= 1:
        return ""

    recent_history = state.dialog_history[-6:-1]  # Последние 5 сообщений
    return "\n".join([
        f"{'Клиент' if h['role'] == 'user' else 'Антон'}: {h['text']}"
        for h in recent_history
    ])


def should_prevent_repeat(state, current_prompt):
    """Проверка на возможные повторы в ответах"""
    assistant_responses = [
        h["text"] for h in state.dialog_history[-4:]
        if h["role"] == "assistant"
    ]

    if len(assistant_responses) >= 2:
        # Если последние 2 ответа очень похожи - добавить указание на разнообразие
        last_two = assistant_responses[-2:]
        similarity_ratio = len(set(last_two[0].split()) & set(last_two[1].split())) / len(set(last_two[0].split()) | set(last_two[1].split()))
        if similarity_ratio > 0.3:  # Более 30% общих слов
            return "\n\nВАЖНО: Не повторяй предыдущий ответ. Задай вопрос про другой аспект (город, этаж, тип дома, документы)."

    return ""


@bot.message_handler(
    func=lambda m: get_user_state(m.chat.id).mode == BotModes.QUICK,
    content_types=["text"],
)
def quick_handler(message):
    chat_id = message.chat.id
    state = get_user_state(chat_id)
    consent = get_user_consent(chat_id)
    if not consent.privacy_accepted:
        show_privacy_consent(chat_id)
        return

    # Сохраняем вопрос в историю (как в dialog_handler)
    state.dialog_history.append({"role": "user", "text": message.text})

    # Получаем контекст из RAG
    rag_context = get_rag_context(message.text)

    # Формируем историю диалога
    history_text = build_history_text(state)

    # Используем общий system_prompt
    system_prompt = build_system_prompt()

    # Проверяем на возможные повторы
    repeat_prevention = should_prevent_repeat(state, "")

    # Формируем full_prompt (аналогично dialog_handler)
    full_prompt = f"""
{system_prompt}

================ КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ ================
{rag_context}

{f"ИСТОРИЯ ДИАЛОГА (ЧТО УЖЕ БЫЛО СКАЗАНО):\n{history_text}\n" if history_text else ""}

НОВЫЙ ВОПРОС КЛИЕНТА:
{message.text}

ТВОЯ ЗАДАЧА ДЛЯ БЫСТРОЙ КОНСУЛЬТАЦИИ:
1. Прочитай ИСТОРИЮ — что клиент УЖЕ сказал
2. Дай ТОЛЬКО новую полезную информацию из КОНТЕКСТА (250-350 символов)
3. НЕ повторяй информацию, которую УЖЕ давал в этом режиме{repeat_prevention}
4. После 1-2 ответов мягко предложи перейти в диалог или оставить заявку
5. Быстрая консультация — это предварительные ответы, а не полный диалог
"""

    response = call_yandex_gpt(full_prompt, user_name=state.name)

    state.dialog_history.append({"role": "assistant", "text": response})
    bot.send_message(chat_id, response)

    # После 2-х ответов в QUICK предлагаем перейти в полноценный диалог
    assistant_count = len([h for h in state.dialog_history if h["role"] == "assistant"])
    if assistant_count >= 2:
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton(
                "💬 Перейти в диалог", callback_data="mode_dialog"
            )
        )
        markup.add(
            types.InlineKeyboardButton(
                "📝 Оставить заявку", callback_data="mode_quiz"
            )
        )
        bot.send_message(
            chat_id,
            f"{state.name}, хотите продолжить обсуждение или перейти к оформлению заявки?",
            reply_markup=markup,
        )


# ========== ГОЛОСОВЫЕ И АУДИО СООБЩЕНИЯ ==========


@bot.message_handler(content_types=["voice"])
def handle_voice(message):
    chat_id = message.chat.id
    state = get_user_state(chat_id)

    # Проверяем согласие
    consent = get_user_consent(chat_id)
    if not consent.privacy_accepted:
        show_privacy_consent(chat_id)
        return

    try:
        # Скачиваем голосовое сообщение
        file_info = bot.get_file(message.voice.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Сохраняем во временный файл
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_file:
            temp_file.write(downloaded_file)
            temp_file_path = temp_file.name

        # Транскрибируем
        recognized_text = transcribe_audio(temp_file_path)

        # Удаляем временный файл
        os.unlink(temp_file_path)

        if recognized_text:
            # Создаем искусственное текстовое сообщение для передачи в существующие хендлеры
            fake_message = type(
                "FakeMessage",
                (),
                {
                    "chat": type("Chat", (), {"id": chat_id})(),
                    "text": f"[VOICE] {recognized_text}",
                    "from_user": message.from_user,
                },
            )()

            # Уведомляем пользователя о распознавании
            if not state.voice_used:
                bot.send_message(
                    chat_id,
                    f"🎤 Расшифровала ваше голосовое сообщение и сейчас отвечу по сути.",
                )
                state.voice_used = True

            # Передаем в существующие хендлеры в зависимости от режима
            if state.mode == BotModes.DIALOG:
                dialog_handler(fake_message)
            elif state.mode == BotModes.QUIZ:
                quiz_handler(fake_message)
            elif state.mode == BotModes.QUICK:
                quick_handler(fake_message)
            else:
                # Если режим не активен - включаем диалог
                state.mode = BotModes.DIALOG
                dialog_handler(fake_message)
        else:
            # Если не удалось распознать
            bot.send_message(
                chat_id,
                "Не получилось разобрать голосовое сообщение. Можно, пожалуйста, коротко написать текстом, что вы хотите сделать с перепланировкой?",
            )

    except Exception as e:
        print(f"❌ Ошибка обработки голосового: {e}")
        bot.send_message(
            chat_id,
            "Не получилось разобрать голосовое сообщение. Можно, пожалуйста, коротко написать текстом, что вы хотите сделать с перепланировкой?",
        )


@bot.message_handler(content_types=["audio"])
def handle_audio(message):
    chat_id = message.chat.id
    state = get_user_state(chat_id)

    # Проверяем согласие
    consent = get_user_consent(chat_id)
    if not consent.privacy_accepted:
        show_privacy_consent(chat_id)
        return

    try:
        # Скачиваем аудиофайл
        file_info = bot.get_file(message.audio.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Сохраняем во временный файл
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_file.write(downloaded_file)
            temp_file_path = temp_file.name

        # Транскрибируем
        recognized_text = transcribe_audio(temp_file_path)

        # Удаляем временный файл
        os.unlink(temp_file_path)

        if recognized_text:
            # Создаем искусственное текстовое сообщение
            fake_message = type(
                "FakeMessage",
                (),
                {
                    "chat": type("Chat", (), {"id": chat_id})(),
                    "text": f"[AUDIO] {recognized_text}",
                    "from_user": message.from_user,
                },
            )()

            # Уведомляем пользователя о распознавании
            if not state.voice_used:
                bot.send_message(
                    chat_id,
                    f"🎵 Расшифровала ваше аудиосообщение и сейчас отвечу по сути.",
                )
                state.voice_used = True

            # Передаем в существующие хендлеры в зависимости от режима
            if state.mode == BotModes.DIALOG:
                dialog_handler(fake_message)
            elif state.mode == BotModes.QUIZ:
                quiz_handler(fake_message)
            elif state.mode == BotModes.QUICK:
                quick_handler(fake_message)
            else:
                # Если режим не активен - включаем диалог
                state.mode = BotModes.DIALOG
                dialog_handler(fake_message)
        else:
            # Если не удалось распознать
            bot.send_message(
                chat_id,
                "Не получилось разобрать аудиосообщение. Можно, пожалуйста, коротко написать текстом, что вы хотите сделать с перепланировкой?",
            )

    except Exception as e:
        print(f"❌ Ошибка обработки аудио: {e}")
        bot.send_message(
            chat_id,
            "Не получилось разобрать аудиосообщение. Можно, пожалуйста, коротко написать текстом, что вы хотите сделать с перепланировкой?",
        )


# ========== ОБРАБОТКА ФАЙЛОВ ==========


@bot.message_handler(content_types=["document", "photo"])
def handle_files(message):
    chat_id = message.chat.id
    bot.send_message(
        chat_id, "📁 Функция анализа планов будет доступна в следующем обновлении."
    )
    show_main_menu(chat_id)


# ========== ТЕСТОВЫЕ КОМАНДЫ ==========


@bot.message_handler(commands=["test_gpt"])
def test_gpt_handler(message):
    chat_id = message.chat.id
    test_response = call_yandex_gpt("Привет! Ответь коротко как дела?")
    bot.send_message(chat_id, f"Тест ЯндексGPT:\n{test_response}")


@bot.message_handler(commands=["test_rag"])
def test_rag_handler(message):
    chat_id = message.chat.id
    if kb:
        test_context = kb.get_rag_context("перепланировка квартиры")
        bot.send_message(
            chat_id, f"Тест RAG (первые 500 символов):\n{test_context[:500]}..."
        )
    else:
        bot.send_message(chat_id, "RAG не инициализирован")


# ========== CONTENT AGENT COMMANDS ==========

@bot.message_handler(commands=["generate_content"])
def generate_content_cmd(message):
    """Генерация контент-плана на неделю"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Команда доступна только администратору")
        return

    import asyncio
    import logging
    logging.info(f"!!! /generate_content called by user_id={message.from_user.id}")

    # Парсим тему из команды (формат: /generate_content Тема: новый год и зимние перепланировки)
    theme = None
    if len(message.text.split()) > 1:
        text_after_command = message.text[len("/generate_content"):].strip()
        if text_after_command.startswith("Тема:"):
            theme = text_after_command[5:].strip()

    # Отвечаем админу сразу
    theme_msg = f" с темой '{theme}'" if theme else ""
    bot.reply_to(message, f"🤖 Генерирую контент-план на неделю{theme_msg}... Это займёт ~30-60 секунд.")

    try:
        # Генерируем посты
        agent = ContentAgent(api_key=YANDEX_API_KEY, model_uri=f"gpt://{FOLDER_ID}/yandexgpt/latest")
        posts = agent.generate_posts(7, theme=theme)

        # Сохраняем в БД
        async def save_posts():
            for post in posts:
                await db.save_post(
                    post['type'],
                    post.get('title', ''),
                    post['body'],
                    post['cta'],
                    post['publish_date']
                )

        asyncio.run(save_posts())

        # Отправляем черновики в соответствующие топики
        drafts = asyncio.run(db.get_draft_posts())
        for post in drafts:
            # Определяем топик по типу поста
            thread_id = THREAD_ID_SEASONAL if post['type'] in ['seasonal', 'живой'] else THREAD_ID_DRAFTS

            text = f"[Тип: {post['type']}]\n\n📌 {post.get('title', '')}\n\n{post['body']}\n\n👉 {post['cta']}"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✅ Утвердить", callback_data=f"approve_{post['id']}"))
            markup.add(types.InlineKeyboardButton("❌ Удалить", callback_data=f"delete_{post['id']}"))

            try:
                bot.send_message(LEADS_GROUP_CHAT_ID, text, reply_markup=markup, message_thread_id=thread_id)
            except Exception as e:
                logging.error(f"Failed to send draft to group: {e}")

        # Логируем в THREAD_ID_LOGS
        log_text = f"✅ Сгенерировано 7 постов в БД\n📝 Черновики отправлены в топики группы\nВремя: {datetime.datetime.now()}"
        try:
            bot.send_message(LEADS_GROUP_CHAT_ID, log_text, message_thread_id=THREAD_ID_LOGS)
        except Exception as e:
            logging.error(f"Failed to send log: {e}")

        # Отвечаем админу
        bot.send_message(message.chat.id, f"✅ Сгенерировано {len(posts)} постов! Черновики отправлены в группу.")

    except Exception as e:
        error_log = f"❌ ОШИБКА\nГенерация контента\nДетали: {str(e)}\nВремя: {datetime.datetime.now()}"
        try:
            bot.send_message(LEADS_GROUP_CHAT_ID, error_log, message_thread_id=THREAD_ID_LOGS)
        except:
            pass
        bot.send_message(message.chat.id, f"❌ Ошибка генерации: {str(e)}")


@bot.message_handler(commands=["add_subscriber"])
def add_subscriber_cmd(message):
    """Добавить подписчика в систему поздравлений (только для ADMIN_ID)"""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещен")
        return

    import asyncio

    # Парсим команду: /add_subscriber @username 15.03.1990 Заметка о клиенте
    parts = message.text.split()
    if len(parts) < 3:
        bot.send_message(message.chat.id, "❌ Формат: /add_subscriber @username DD.MM.YYYY [заметка]")
        return

    username = parts[1].lstrip('@')
    birthday = parts[2]

    # Проверяем формат даты
    try:
        day, month, year = birthday.split('.')
        day, month, year = int(day), int(month), int(year)
        if not (1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2100):
            raise ValueError
    except:
        bot.send_message(message.chat.id, "❌ Неверный формат даты. Используйте DD.MM.YYYY")
        return

    notes = ' '.join(parts[3:]) if len(parts) > 3 else None

    # Получаем user_id по username (упрощенная версия)
    # В реальности нужно использовать bot.get_chat_member() или кэшировать пользователей
    user_id = None
    try:
        # Для упрощения используем ADMIN_ID как placeholder
        # В реальной реализации нужно получить user_id из username
        user_id = ADMIN_ID  # Временный placeholder
        first_name = username
        last_name = None
    except:
        bot.send_message(message.chat.id, f"❌ Не удалось найти пользователя @{username}")
        return

    # Добавляем в базу
    try:
        asyncio.run(db.add_subscriber(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            birthday=birthday,
            notes=notes
        ))
        bot.send_message(message.chat.id, f"✅ Подписчик @{username} добавлен с днем рождения {birthday}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка добавления: {str(e)}")


@bot.message_handler(commands=["list_birthdays"])
def list_birthdays_cmd(message):
    """Показать предстоящие дни рождения (только для ADMIN_ID)"""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещен")
        return

    import asyncio

    try:
        upcoming = asyncio.run(db.get_upcoming_birthdays(7))

        if not upcoming:
            bot.send_message(message.chat.id, "📅 Нет предстоящих дней рождения на следующей неделе")
            return

        response = "🎂 Предстоящие дни рождения (следующие 7 дней):\n\n"
        for person in upcoming:
            days = person['days_until_birthday']
            if days == 0:
                when = "🎉 СЕГОДНЯ!"
            elif days == 1:
                when = "завтра"
            else:
                when = f"через {days} дней"

            name = person.get('first_name') or person.get('username') or f"ID:{person['user_id']}"
            birthday = person['birthday']
            response += f"• {name} - {birthday} ({when})\n"

        bot.send_message(message.chat.id, response)

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка получения списка: {str(e)}")


@bot.message_handler(commands=["generate_greetings"])
def generate_greetings_cmd(message):
    """Генерировать поздравления для предстоящих дней рождения (только для ADMIN_ID)"""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещен")
        return

    import asyncio
    import datetime

    try:
        upcoming = asyncio.run(db.get_upcoming_birthdays(7))

        if not upcoming:
            bot.send_message(message.chat.id, "📅 Нет предстоящих дней рождения для генерации поздравлений")
            return

        generated_count = 0

        for person in upcoming:
            # Генерируем персональное поздравление
            agent = ContentAgent(api_key=YANDEX_API_KEY, model_uri=f"gpt://{FOLDER_ID}/yandexgpt/latest")
            name = person.get('first_name') or person.get('username') or "друг"
            birthday = person['birthday']

            # Используем шаблонный метод для поздравлений
            post = agent.generate_birthday_congrats_template(person_name=name, date=birthday)

            # Добавляем подпись компании программно
            full_body = f"{post['body']}\n\nС наилучшими пожеланиями,\nКоманда «Пархоменко и компания» ❤️"

            # Сохраняем как черновик
            publish_date = datetime.datetime.now() + datetime.timedelta(days=person['days_until_birthday'])

            post_id = asyncio.run(db.save_post(
                post_type='поздравление',
                title=post.get('title', f"Поздравление для {name}"),
                body=full_body,
                cta=post['cta'],
                publish_date=publish_date
            ))

            # Отправляем в топик черновиков
            text = f"[Тип: поздравление]\n\n🎂 {name}\n\n{post['body']}\n\n{post['cta']}"
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✅ Утвердить", callback_data=f"approve_{post_id}"))
            markup.add(types.InlineKeyboardButton("❌ Удалить", callback_data=f"delete_{post_id}"))

            try:
                bot.send_message(LEADS_GROUP_CHAT_ID, text, reply_markup=markup, message_thread_id=THREAD_ID_DRAFTS)
                generated_count += 1
            except Exception as e:
                print(f"Failed to send greeting: {e}")

        if generated_count > 0:
            bot.send_message(message.chat.id, f"✅ Сгенерировано {generated_count} поздравлений! Черновики отправлены в топик 'Черновики и идеи'.")
        else:
            bot.send_message(message.chat.id, "❌ Не удалось сгенерировать поздравления")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка генерации поздравлений: {str(e)}")


@bot.message_handler(commands=["generate_welcome"])
def generate_welcome_cmd(message):
    """Генерировать приветственное сообщение для потенциального клиента (только для ADMIN_ID)"""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещен")
        return

    import asyncio
    import datetime

    # Парсим имя из команды: /generate_welcome Иван или просто /generate_welcome
    parts = message.text.split()
    person_name = None
    if len(parts) > 1:
        person_name = ' '.join(parts[1:])  # всё после команды как имя

    try:
        # Генерируем приветственное сообщение
        agent = ContentAgent(api_key=YANDEX_API_KEY, model_uri=f"gpt://{FOLDER_ID}/yandexgpt/latest")
        post = agent.generate_welcome_post(person_name=person_name)

        # Сохраняем как черновик
        publish_date = datetime.datetime.now() + datetime.timedelta(days=1)  # Завтра в 10:00
        publish_date = publish_date.replace(hour=10, minute=0, second=0, microsecond=0)

        post_id = asyncio.run(db.save_post(
            post_type='приветствие',
            title=post.get('title', f"Приветствие для {'нового подписчика' if not person_name else person_name}"),
            body=post['body'],
            cta=post['cta'],
            publish_date=publish_date
        ))

        # Отправляем в топик черновиков
        text = f"[Тип: приветствие]\n\n{post['body']}\n\n{post['cta']}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Утвердить", callback_data=f"approve_{post_id}"))
        markup.add(types.InlineKeyboardButton("❌ Удалить", callback_data=f"delete_{post_id}"))

        try:
            bot.send_message(LEADS_GROUP_CHAT_ID, text, reply_markup=markup, message_thread_id=THREAD_ID_DRAFTS)

            # Логируем
            log_text = f"✅ Приветствие сгенерировано\nТип: приветствие\nПубликация: {publish_date.strftime('%d.%m.%Y %H:%M')}\nВремя: {datetime.datetime.now()}"
            try:
                bot.send_message(LEADS_GROUP_CHAT_ID, log_text, message_thread_id=THREAD_ID_LOGS)
            except Exception as e:
                print(f"Failed to send welcome log: {e}")

            bot.send_message(message.chat.id, f"✅ Приветственное сообщение сгенерировано! Черновик отправлен в топик 'Черновики и идеи'.")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка отправки приветствия: {str(e)}")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка генерации приветствия: {str(e)}")


@bot.message_handler(commands=["show_plan"])
def show_plan_cmd(message):
    """Показать контент-план"""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещен")
        return

    import asyncio

    # Получаем черновики
    drafts = asyncio.run(db.get_draft_posts())

    if not drafts:
        bot.send_message(message.chat.id, "📭 Контент-план пуст. Используй /generate_content для генерации.")
        return

    # Отправляем черновики в соответствующие топики
    for post in drafts:
        # Определяем топик по типу поста
        thread_id = THREAD_ID_SEASONAL if post['type'] in ['seasonal', 'живой'] else THREAD_ID_DRAFTS

        text = f"[Тип: {post['type']}]\n\n📌 {post.get('title', '')}\n\n{post['body']}\n\n👉 {post['cta']}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Утвердить", callback_data=f"approve_{post['id']}"))
        markup.add(types.InlineKeyboardButton("❌ Удалить", callback_data=f"delete_{post['id']}"))

        try:
            bot.send_message(LEADS_GROUP_CHAT_ID, text, reply_markup=markup, message_thread_id=thread_id)
        except Exception as e:
            logging.error(f"Failed to send draft to group: {e}")

    # Логируем в THREAD_ID_LOGS
    log_text = f"📋 Показаны черновики ({len(drafts)} шт.)\nВремя: {datetime.datetime.now()}"
    try:
        bot.send_message(LEADS_GROUP_CHAT_ID, log_text, message_thread_id=THREAD_ID_LOGS)
    except Exception as e:
        logging.error(f"Failed to send log: {e}")

    # Отвечаем админу
    bot.send_message(message.chat.id, f"✅ Черновики ({len(drafts)} шт.) отправлены в группу.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("approve_") or call.data.startswith("delete_"))
def content_callback_handler(call):
    """Обработка кнопок approve/delete"""
    if call.message.chat.id != LEADS_GROUP_CHAT_ID:
        return

    post_id = int(call.data.split('_')[1])

    import asyncio

    if call.data.startswith("approve_"):
        # СНАЧАЛА получаем информацию о посте
        drafts = asyncio.run(db.get_draft_posts())
        post = next((p for p in drafts if p['id'] == post_id), None)

        if not post:
            bot.answer_callback_query(call.id, "❌ Пост не найден")
            return

        # Устанавливаем publish_date и статус (инкрементальные даты)
        import datetime
        from datetime import datetime, timedelta

        # Получить максимальную дату среди approved постов
        max_date = asyncio.run(db.get_max_publish_date(status='approved'))

        if max_date is None:
            # Первый approved пост → завтра в 10:00
            next_date = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        else:
            # Следующий пост → +1 день от последнего
            next_date = max_date + timedelta(days=1)

        # Обновить пост
        asyncio.run(db.update_content_plan_entry(
            post_id=post_id,
            status='approved',
            publish_date=next_date.strftime('%Y-%m-%d %H:%M:%S')
        ))

        # Редактируем сообщение
        new_text = f"✅ УТВЕРЖДЁН\nПубликация: {next_date.strftime('%d.%m.%Y %H:%M')}\n\n{call.message.text}"
        bot.edit_message_text(new_text, call.message.chat.id, call.message.message_id)

        # Логируем
        log_text = f"✅ Пост #{post_id} утверждён\nТип: {post['type']}\nПубликация: {next_date.strftime('%d.%m.%Y %H:%M')}\nВремя: {datetime.datetime.now()}"
        try:
            bot.send_message(LEADS_GROUP_CHAT_ID, log_text, message_thread_id=THREAD_ID_LOGS)
        except Exception as e:
            print(f"Failed to send approval log: {e}")

        bot.answer_callback_query(call.id, f"✅ Пост утверждён! Публикация: {next_date.strftime('%d.%m в %H:%M')}")

    elif call.data.startswith("delete_"):
        # Получаем информацию о посте перед удалением
        drafts = asyncio.run(db.get_draft_posts())
        post = next((p for p in drafts if p['id'] == post_id), None)

        # Удаляем пост
        asyncio.run(db.delete_post(post_id))

        # Редактируем сообщение
        if post:
            new_text = f"❌ УДАЛЁН\n(был: {post.get('title', 'Без заголовка')})"
        else:
            new_text = "❌ УДАЛЁН"
        bot.edit_message_text(new_text, call.message.chat.id, call.message.message_id)

        # Логируем
        post_type = post['type'] if post else 'неизвестно'
        log_text = f"❌ Пост #{post_id} удалён\nТип: {post_type}\nВремя: {datetime.datetime.now()}"
        try:
            bot.send_message(LEADS_GROUP_CHAT_ID, log_text, message_thread_id=THREAD_ID_LOGS)
        except Exception as e:
            print(f"Failed to send deletion log: {e}")

        bot.answer_callback_query(call.id, "❌ Пост удалён")


# ========== ЗАПУСК ==========

import asyncio

# Подключаемся к БД в синхронном контексте
try:
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(db.connect())
except ImportError:
    # Если nest_asyncio не установлен, создаём новый event loop
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(db.connect())

# Запускаем автопостер в отдельном потоке
import threading
poster_thread = threading.Thread(target=lambda: asyncio.run(run_auto_poster(bot)), daemon=True)
poster_thread.start()

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
        time.sleep(15)
