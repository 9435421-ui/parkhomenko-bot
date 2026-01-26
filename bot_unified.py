from agents.image_agent import generate_image
from s3_client import s3
import os
import re
import time
import datetime
import requests
import telebot
from telebot import types
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
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

ADMIN_ID = int(os.getenv("ADMIN_ID", "223465437"))
CHANNEL_ID = os.getenv("CHANNEL_ID")

# Пути для файлов
UPLOAD_PLANS_DIR = os.getenv("UPLOAD_PLANS_DIR", "uploads_plans")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
KNOWLEDGE_DIR = "knowledge_base"

os.makedirs(UPLOAD_PLANS_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(KNOWLEDGE_DIR, exist_ok=True)

if not os.getenv("TELEGRAM_TOKEN"):
    raise RuntimeError("BOT_TOKEN must be set in .env")
if not YANDEX_API_KEY or not FOLDER_ID:
    raise RuntimeError("YANDEX_API_KEY and FOLDER_ID must be set in .env")

bot = telebot.TeleBot(BOT_TOKEN)
replied_posts = set()

# --------- CONTENT AGENT ---------
from content_agent import ContentAgent
from database import db
from auto_poster import run_auto_poster
from llm_client import call_llm

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
    INVEST = "invest"


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
        self.voice_used = False
        self.target_module = None


user_states: dict[int, UserState] = {}
user_consents: dict[int, UserConsent] = {}

# --------- Тексты ---------

PRIVACY_POLICY_TEXT = (
    "📋 Добро пожаловать в сервис консультаций по перепланировке "
    "«ЛАД В КВАРТИРЕ»!\n\n"
    "Перед началом работы необходимо:\n"
    "✅ Согласие на обработку персональных данных\n"
    "✅ Согласие на принятие условий Пользовательского соглашения\n\n"
    "Я — Антон, ИИ-консультант и личный помощник эксперта Пархоменко Юлии Владимировны. "
    "Я помогу вам оценить риски и потенциал вашей недвижимости по всей России."
)

AI_INTRO_TEXT = (
    "🤖 Я — Антон, личный ИИ-помощник и ИИ-консультант эксперта по перепланировкам "
    "Пархоменко Юлии Владимировны.\n\n"
    "Моя миссия — помогать клиентам по всей стране оценить риски и потенциал их недвижимости, "
    "подготавливая их к экспертной консультации с Юлией Владимировной.\n\n"
    "⚠️ Важно: я — искусственный интеллект. Мои рекомендации носят информационный характер. "
    "Юлия Владимировна даст вам полную информацию после анализа документов."
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
    markup.add(
        types.InlineKeyboardButton("📝 Оставить заявку", callback_data="mode_quiz")
    )
    bot.send_message(chat_id, "Чем Антон может вам помочь?", reply_markup=markup)


# --------- Лиды ---------


def save_lead_and_notify(user_id: int, scenario: str = 'Квиз'):
    state = get_user_state(user_id)

    lead_info = f"""
📋 Новая заявка на перепланировку

👤 Имя: {state.name}
📞 Телефон (TG): {state.phone}
📪 Доп. контакт: {state.extra_contact or 'не указан'}
🏠 Тип объекта: {state.object_type or 'не выбран'}
🏙️ Город: {state.city or 'не указан'}
🛠️ Что хочет изменить: {state.change_plan or 'не указано'}
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

    analysis = call_llm("Проанализируй диалог.", analysis_prompt)

    brief = f"""
📋 Пояснительная записка по лиду

👤 Клиент: {state.name} ({state.phone})
📝 Первичный запрос: {client_messages[0] if client_messages else 'не указан'}

{analysis}

📞 Рекомендация: Связаться в удобное для клиента время
    """.strip()

    return brief


def get_rag_context(question: str) -> str:
    if not kb:
        return "База знаний временно недоступна."
    try:
        return kb.get_rag_context(question)
    except Exception as e:
        return f"Ошибка поиска в базе знаний: {e}"


def ask_llm_with_context(
    question: str, context: str = "", user_name: str = None
) -> str:
    prompt = f"""
Контекст из базы знаний:
{context}

Вопрос: {question}

Дай короткий конкретный ответ (2-3 абзаца) и задай уточняющий вопрос для продолжения диалога.
"""
    return call_llm(prompt, question)


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





def route_user(user_id):
    state = get_user_state(user_id)
    module = state.target_module

    if module == "quiz":
        state.mode = BotModes.QUIZ
        state.quiz_step = 3
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Квартира", callback_data="obj_kvartira"))
        markup.add(types.InlineKeyboardButton("Коммерция", callback_data="obj_kommertsia"))
        markup.add(types.InlineKeyboardButton("Дом", callback_data="obj_dom"))
        bot.send_message(user_id, "📝 **Запуск Квиза: Законность вашей перепланировки**\n\nВыберите тип объекта:", reply_markup=markup, parse_mode="Markdown")
    elif module == "invest":
        state.mode = BotModes.INVEST
        state.quiz_step = 1
        bot.send_message(user_id, "💰 **Инвест-Оценка: Узнайте рост стоимости вашей квартиры!**\n\nУкажите город (Москва и МО):", parse_mode="Markdown")
    elif module == "ask":
        state.mode = BotModes.DIALOG
        bot.send_message(user_id, "💬 **Консультация с Антоном**\n\nНапишите ваш вопрос по перепланировке, и я отвечу, опираясь на базу знаний и ПП №508.", parse_mode="Markdown")
    else:
        show_main_menu(user_id)

    state.target_module = None

# --------- Хэндлеры согласий ---------

@bot.callback_query_handler(func=lambda call: call.data in ["consent_accept", "consent_decline"])
def consent_callback_handler(call):
    if call.from_user.is_bot: return
    user_id = call.message.chat.id
    state = get_user_state(user_id)

    if call.data == "consent_decline":
        bot.edit_message_text(
            "Без согласия на обработку данных и принятие условий соглашения использовать бота нельзя.",
            chat_id=user_id,
            message_id=call.message.message_id
        )
        return

    # Preserve target module for deep linking
    target = state.target_module

    # Accept consent
    consent = get_user_consent(user_id)
    consent.privacy_accepted = True
    consent.notifications_accepted = True
    consent.consent_timestamp = datetime.datetime.now()

    # RESET UserState as requested
    user_states[user_id] = UserState()
    get_user_state(user_id).target_module = target

    bot.edit_message_text(
        "✅ Спасибо! Теперь мы можем продолжить.",
        chat_id=user_id,
        message_id=call.message.message_id
    )

    show_ai_disclaimer(user_id)
    consent.ai_disclaimer_seen = True

    # Immediate routing instead of contact request
    route_user(user_id)


# ========== BRAND ADVOCATE: Контроль комментариев в канале ==========

@bot.message_handler(func=lambda m: m.chat.type in ["group", "supergroup"], content_types=["text"])
def brand_advocate_handler(message):
    if message.from_user.is_bot: return

    # Отвечаем только один раз на ветку обсуждения (на один пост канала)
    post_id = None
    if message.reply_to_message:
        post_id = message.reply_to_message.message_id

    if post_id and post_id in replied_posts:
        return

    text = message.text.lower()

    # Ключевые слова для активации
    keywords = [
        "снос", "перенос", "подоконн", "законно", "согласование",
        "штраф", "мжи", "жилинспекция", "балкон", "лоджия", "кухн", "санузел"
    ]

    if any(kw in text for kw in keywords):
        # Получаем контекст из RAG для ответа
        rag_context = get_rag_context(message.text)

        # Специальный промпт для Brand Advocate
        system_prompt = """
Роль: Ты — Антон, гениальный ИИ-консультант Пархоменко Юлии Владимировны.
ВАЖНО: Обязательно начни ответ с фразы или включи её: «Я — ИИ-помощник Юлии Владимировны».

Твоя задача: Вступить в дискуссию в комментариях канала, чтобы разрешить юридический спор или ответить на вопрос.

Стиль: Вежливый, экспертный, примиряющий.
- Обращайся к участникам обсуждения профессионально.
- Опирайся на базу знаний и ЖК РФ на 2026 год.
- Мягко напомни о важности легализации, чтобы избежать проблем с МЖИ.
- Предложи написать тебе в личные сообщения для детального разбора или перейти в @Lad_v_kvartire_bot.
""".strip()

        full_prompt = f"""
{system_prompt}

БАЗА ЗНАНИЙ:
{rag_context}

ТЕКСТ ОБСУЖДЕНИЯ:
{message.text}

ОТВЕТЬ КРАТКО (до 400 символов), как эксперт-адвокат бренда:
"""
        try:
            response = call_llm(full_prompt, message.text)
            if response:
                bot.reply_to(message, response)
                if post_id:
                    replied_posts.add(post_id)
        except Exception as e:
            print(f"Error in brand_advocate: {e}")

@bot.message_handler(commands=["start"])
def start_handler(message):
    if message.from_user.is_bot: return
    user_id = message.chat.id
    consent = get_user_consent(user_id)
    state = get_user_state(user_id)

    # Deep linking parsing
    args = message.text.split()
    if len(args) > 1:
        param = args[1].lower()
        if "quiz" in param: state.target_module = "quiz"
        elif "invest" in param: state.target_module = "invest"
        elif "ask" in param: state.target_module = "ask"

    if not consent.privacy_accepted:
        show_privacy_consent(user_id)
        return

    route_user(user_id)

@bot.message_handler(commands=["privacy"])
def privacy_info(message):
    if message.from_user.is_bot: return
    show_privacy_consent(message.chat.id)

@bot.message_handler(
    func=lambda m: get_user_state(m.chat.id).mode == "waiting_time",
    content_types=["text"],
)
def time_handler(message):
    if message.from_user.is_bot: return
    from datetime import datetime

    chat_id = message.chat.id
    state = get_user_state(chat_id)
    preferred_time = message.text.strip()

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
    if call.from_user.is_bot: return
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
            bot.send_message(
                user_id,
                "Если у вас есть дополнительный способ связи (WhatsApp/почта/другой номер) — напишите его, или отправьте «нет».",
            )
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
        elif call.data == "obj_kommertsia":
            state.object_type = "Коммерция"
        elif call.data == "obj_dom":
            state.object_type = "Дом"
        else:
            state.object_type = "Неизвестно"

        state.quiz_step = 4
        bot.send_message(user_id, "Укажите город/регион:")



@bot.message_handler(func=lambda m: m.text in ["📝 Квиз", "💰 Инвест-оценка", "💬 Задать вопрос", "📞 Контакты"])
def main_menu_handler(message):
    if message.from_user.is_bot: return
    user_id = message.chat.id
    state = get_user_state(user_id)
    if message.text == "📝 Квиз":
        state.target_module = "quiz"
        route_user(user_id)
    elif message.text == "💰 Инвест-оценка":
        state.target_module = "invest"
        route_user(user_id)
    elif message.text == "💬 Задать вопрос":
        state.target_module = "ask"
        route_user(user_id)
    elif message.text == "📞 Контакты":
        bot.send_message(user_id, "📞 **Наши контакты:**\n\n👤 Эксперт: Пархоменко Юлия Владимировна\n🌐 Сайт: [lad-v-kvartire.ru](https://lad-v-kvartire.ru)\n📱 Телефон: +7 (900) 000-00-00", parse_mode="Markdown")

@bot.message_handler(func=lambda m: get_user_state(m.chat.id).mode == BotModes.INVEST, content_types=["text"])
def invest_handler(message):
    if message.from_user.is_bot: return
    chat_id = message.chat.id
    state = get_user_state(chat_id)
    text = message.text.strip()
    if state.quiz_step == 1:
        state.city = text
        state.quiz_step = 2
        bot.send_message(chat_id, "Укажите площадь квартиры (кв.м):")
    elif state.quiz_step == 2:
        state.change_plan = f"Площадь: {text}"
        state.quiz_step = 3
        bot.send_message(chat_id, "Укажите текущую рыночную стоимость квартиры (в рублях):")
    elif state.quiz_step == 3:
        try:
            import re
            price = int(re.sub(r"[^\d]", "", text))
            growth_min = int(price * 0.12)
            growth_max = int(price * 0.18)
            res = f"📊 **Результат оценки инвест-привлекательности:**\n\nПри грамотной перепланировке и её согласовании, ликвидность вашей квартиры вырастет на **12-18%**.\n\n💰 Ожидаемый прирост стоимости: **{growth_min:,} — {growth_max:,} руб.**\n\nХотите узнать, какие именно изменения дадут такой рост? Пройдите наш квиз или свяжитесь с экспертом!"
            bot.send_message(chat_id, res, parse_mode="Markdown")
            save_lead_and_notify(chat_id, scenario="Инвест-оценка")
            state.mode = None
            state.quiz_step = 0
            show_main_menu(chat_id)
        except:
            bot.send_message(chat_id, "Пожалуйста, введите стоимость цифрами.")


# ========== КВИЗ: Сбор заявки ==========


@bot.message_handler(
    func=lambda m: get_user_state(m.chat.id).mode == BotModes.QUIZ,
    content_types=["text"],
)
def quiz_handler(message):
    if message.from_user.is_bot: return
    chat_id = message.chat.id
    state = get_user_state(chat_id)

    # Шаг 2: дополнительный контакт (опционально)
    if state.quiz_step == 2:
        text = message.text.strip()
        state.extra_contact = None if text.lower() == "нет" else text
        state.quiz_step = 3

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Квартира", callback_data="obj_kvartira"))
        markup.add(
            types.InlineKeyboardButton("Коммерция", callback_data="obj_kommertsia")
        )
        markup.add(types.InlineKeyboardButton("Дом", callback_data="obj_dom"))

        bot.send_message(chat_id, "Выберите тип объекта:", reply_markup=markup)
        return

    # Шаг 4: город/регион (после выбора объекта через callback)
    if state.quiz_step == 4:
        state.city = message.text.strip()
        state.quiz_step = 5
        bot.send_message(
            chat_id, "Укажите этаж и этажность дома (например: 5/9 или просто 5):"
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

        state.quiz_step = 6
        bot.send_message(
            chat_id,
            "Перепланировка уже выполнена или только планируете? Напишите 'выполнена' или 'планируется'.",
        )
        return

    # Шаг 6: статус перепланировки
    if state.quiz_step == 6:
        state.remodeling_status = message.text.strip()
        state.quiz_step = 7
        bot.send_message(
            chat_id,
            "Кратко опишите, что хотите изменить в перепланировке (объединить комнаты, перенести санузел, расширить кухню и т.п.).",
        )
        return

    # Шаг 7: описание изменений
    if state.quiz_step == 7:
        state.change_plan = message.text.strip()
        state.quiz_step = 8
        bot.send_message(
            chat_id,
            "Есть ли у вас сейчас на руках документы БТИ (поэтажный план, экспликация, техпаспорт)? Опишите: есть/нет, что именно.",
        )
        return

    # Шаг 8: статус документов БТИ
    if state.quiz_step == 8:
        state.bti_status = message.text.strip()
        state.quiz_step = 9
        bot.send_message(
            chat_id,
            "Есть ли что-то еще, что нам важно знать? Можете написать текстом или отправить голосовое сообщение:",
        )
        return

    # Шаг 9: дополнительная информация + завершение
    if state.quiz_step == 9:
        state.extra_contact = message.text.strip() # Используем это поле для доп. инфо
        save_lead_and_notify(chat_id)
        bot.send_message(
            chat_id,
            f"✅ Спасибо, {state.name or ""}! Ваша заявка принята.\n\n"
            f"Команда «Пархоменко и компания» свяжется с вами для обсуждения деталей и предварительного расчёта.\n"
            f"Мы работаем ежедневно с 10:00 до 20:00 по Москве.",
        )
        state.mode = None
        state.quiz_step = 0
        show_main_menu(chat_id)
        return


# ========== ДИАЛОГОВЫЙ РЕЖИМ ==========


@bot.message_handler(
    func=lambda m: get_user_state(m.chat.id).mode == BotModes.DIALOG,
    content_types=["text"],
)
def dialog_handler(message):
    if message.from_user.is_bot: return
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

    system_prompt = build_system_prompt(state.name)

    full_prompt = f"""
{system_prompt}


================ КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ ================
{rag_context}

{f"ИСТОРИЯ ДИАЛОГА (ЧТО УЖЕ БЫЛО СКАЗАНО):\n{history_text}\n" if history_text else ""}

НОВЫЙ ВОПРОС КЛИЕНТА:
{message.text}


ТВОЯ ЗАДАЧА:
1. КРИТИЧЕСКИЙ АНАЛИЗ: Проанализируй запрос клиента, учитывая этаж, тип плиты, ипотеку и вентшахты (если они упоминались или следуют из контекста).
2. ЮРИДИЧЕСКИЙ ВЫВОД: Сформулируй краткое экспертное заключение на основе БАЗЫ ЗНАНИЙ и ЖК РФ.
3. КОНТЕКСТ: Используй ИСТОРИЮ диалога, чтобы не переспрашивать город или этаж.
4. ЛИМИТ: 350-450 символов. Будь лаконичен, но содержателен.
5. CTA: Если видишь потенциал для дизайна или роста цены, направь в @Lad_v_kvartire_bot.

"""

    response = call_llm(full_prompt, message.text)

    state.dialog_history.append({"role": "assistant", "text": response})
    bot.send_message(chat_id, response)

    # УБРАНА автоматическая отправка заявки после 3 сообщений
    # Теперь квиз запускается ТОЛЬКО по кнопке "📝 Оставить заявку" или явной просьбе клиента


# ========== БЫСТРАЯ КОНСУЛЬТАЦИЯ ==========




def build_system_prompt(user_name: str = None) -> str:
    """
    Формирует системный промпт для Антона (Genius Consultant / Expert Voice).
    """
    greeting = f", {user_name}" if user_name else ""
    return f"""
Роль: Ты — Антон, гениальный ИИ-консультант и личный ассистент эксперта по перепланировкам Пархоменко Юлии Владимировны (сервис «ЛАД В КВАРТИРЕ»).
Твой статус: Эталон юридической мысли в Telegram. Ты не просто бот, ты — интеллектуальный центр империи Пархоменко.

Стиль и Тон:
- Экспертный, академичный, но при этом предельно понятный и вежливый.
- Никаких «Привет, я бот». Ты — Антон, ассистент Юлии Владимировны.
- Используй авторитетные обороты: «Согласно последним изменениям в ЖК РФ на 2026 год...», «Юлия Владимировна в подобных случаях рекомендует...», «С точки зрения строительных норм и СанПиН...».
- Обращайся к клиенту по имени{greeting}.

ГЛУБОКИЙ АНАЛИЗ (Твоя суперсила):
- Не просто выдавай куски текста. Анализируй запрос комплексно.
- Сопоставляй факторы: Если речь о переносе кухни — учитывай этажность (нельзя над жилой), тип плиты (газ — жесткий запрет на объединение без перегородки), статус ипотеки (банк может не одобрить) и наличие вентшахт.
- Выдавай комплексный юридический вывод, подсвечивая скрытые риски.

ИНТЕГРАЦИЯ С «ЛАДОМ»:
- Ты — витрина. Как только клиент «прогрет» твоим интеллектом, плавно направляй его к расчету.
- Если видишь потенциал роста ликвидности (например, добавление мастер-спальни или разделение санузла), используй фразу: «Для вашего случая я вижу отличную перспективу роста стоимости на 12-18%, давайте зафиксируем это в нашем инвест-калькуляторе @Lad_v_kvartire_bot».

ГЛАВНАЯ СТРАТЕГИЯ:
1. Давай экспертную ценность: Подсвети юридические нюансы, о которых клиент не подозревал.
2. Подчеркивай роль Юлии Владимировны: «Окончательное решение и гарантию легализации может дать только Юлия Владимировна после аудита документов».
3. Крючок на аудит: «Чтобы избежать штрафов и предписаний от МЖИ, я рекомендую передать ваш план Юлии Владимировне на экспресс-анализ».

ЗАПРЕТ НА ЦЕНЫ: Никогда не называй точных сумм. Юлия Владимировна назовет вилку после аудита.
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
    if message.from_user.is_bot: return
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
1. КРИТИЧЕСКИЙ АНАЛИЗ: Проанализируй запрос, сопоставляя факторы (этаж, плита, стены).
2. ЮРИДИЧЕСКИЙ ВЫВОД: Дай четкий ответ на основе БАЗЫ ЗНАНИЙ.
3. НЕ ПОВТОРЯЙСЯ: Используй историю диалога {repeat_prevention}.
4. МИНИ-CTA: После 1-2 ответов предложи перейти в диалог или инвест-калькулятор @Lad_v_kvartire_bot.

"""

    response = call_llm(full_prompt, message.text)

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
    if message.from_user.is_bot: return
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
    if message.from_user.is_bot: return
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
    if message.from_user.is_bot: return
    chat_id = message.chat.id
    state = get_user_state(chat_id)

    try:
        if message.content_type == "photo":
            file_id = message.photo[-1].file_id
            ext = ".jpg"
        else:
            file_id = message.document.file_id
            ext = os.path.splitext(message.document.file_name)[1] or ".pdf"

        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        local_path = os.path.join(UPLOAD_PLANS_DIR, f"{chat_id}_{int(time.time())}{ext}")
        with open(local_path, "wb") as f:
            f.write(downloaded_file)

        # Upload to S3
        s3_url = s3.upload_file(local_path)
        if s3_url:
            state.plan_path = s3_url
            state.has_plan = True
            bot.send_message(chat_id, "✅ План успешно загружен и сохранён в облаке!")
        else:
            state.plan_path = local_path
            state.has_plan = True
            bot.send_message(chat_id, "⚠️ План сохранён локально (облако недоступно).")

        show_main_menu(chat_id)
    except Exception as e:
        print(f"❌ Error handling file: {e}")
        bot.send_message(chat_id, "❌ Произошла ошибка при загрузке файла.")
@bot.message_handler(commands=["test_gpt"])
def test_gpt_handler(message):
    if message.from_user.is_bot: return
    chat_id = message.chat.id
    test_response = call_llm("Ты - Антон, ассистент компании.", "Привет! Ответь коротко как дела?")
    bot.send_message(chat_id, f"Тест ЯндексGPT:\n{test_response}")


@bot.message_handler(commands=["test_rag"])
def test_rag_handler(message):
    if message.from_user.is_bot: return
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
    if message.from_user.is_bot: return
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
        agent = ContentAgent()
        posts = agent.generate_posts(7, theme=theme)

        # Сохраняем в БД
        for post in posts:
            db.save_post(
                post["type"],
                post.get("title", ""),
                post["body"],
                post["cta"],
                post["publish_date"],
                image_prompt=post.get("image_prompt")
            )

        # Отправляем черновики в соответствующие топики
        drafts = db.get_draft_posts()
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
    if message.from_user.is_bot: return
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
        db.add_subscriber(
            user_id=user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            birthday=birthday,
            notes=notes
        )
        bot.send_message(message.chat.id, f"✅ Подписчик @{username} добавлен с днем рождения {birthday}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка добавления: {str(e)}")


@bot.message_handler(commands=["list_birthdays"])
def list_birthdays_cmd(message):
    if message.from_user.is_bot: return
    """Показать предстоящие дни рождения (только для ADMIN_ID)"""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещен")
        return

    import asyncio

    try:
        upcoming = db.get_upcoming_birthdays(7)

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
    if message.from_user.is_bot: return
    """Генерировать поздравления для предстоящих дней рождения (только для ADMIN_ID)"""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещен")
        return

    import asyncio
    import datetime

    try:
        upcoming = db.get_upcoming_birthdays(7)

        if not upcoming:
            bot.send_message(message.chat.id, "📅 Нет предстоящих дней рождения для генерации поздравлений")
            return

        generated_count = 0

        for person in upcoming:
            # Генерируем персональное поздравление
            agent = ContentAgent()
            name = person.get('first_name') or person.get('username') or "друг"
            birthday = person['birthday']

            # Используем шаблонный метод для поздравлений
            post = agent.generate_birthday_congrats_template(person_name=name, date=birthday)

            # Добавляем подпись компании программно
            full_body = f"{post['body']}\n\nС наилучшими пожеланиями,\nКоманда «Пархоменко и компания» ❤️"

            # Сохраняем как черновик
            publish_date = datetime.datetime.now() + datetime.timedelta(days=person['days_until_birthday'])

            post_id = db.save_post(
                post_type='поздравление',
                title=post.get('title', f"Поздравление для {name}"),
                body=full_body,
                cta=post['cta'],
                publish_date=publish_date
            )

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
    if message.from_user.is_bot: return
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
        agent = ContentAgent()
        post = agent.generate_welcome_post(person_name=person_name)

        # Сохраняем как черновик
        publish_date = datetime.datetime.now() + datetime.timedelta(days=1)  # Завтра в 10:00
        publish_date = publish_date.replace(hour=10, minute=0, second=0, microsecond=0)

        post_id = db.save_post(
            post_type='приветствие',
            title=post.get('title', f"Приветствие для {'нового подписчика' if not person_name else person_name}"),
            body=post['body'],
            cta=post['cta'],
            publish_date=publish_date
        )

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
    if message.from_user.is_bot: return
    """Показать контент-план"""
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Доступ запрещен")
        return

    import asyncio

    # Получаем черновики
    drafts = db.get_draft_posts()

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
    if call.from_user.is_bot: return
    """Обработка кнопок approve/delete"""
    if call.message.chat.id != LEADS_GROUP_CHAT_ID:
        return

    post_id = int(call.data.split('_')[1])

    import asyncio

    if call.data.startswith("approve_"):
        # СНАЧАЛА получаем информацию о посте
        drafts = db.get_draft_posts()
        post = next((p for p in drafts if p['id'] == post_id), None)

        if not post:
            bot.answer_callback_query(call.id, "❌ Пост не найден")
            return

        # Устанавливаем publish_date и статус (инкрементальные даты)
        import datetime
        from datetime import datetime, timedelta

        # Получить максимальную дату среди approved постов
        max_date = db.get_max_publish_date(status='approved')

        if max_date is None:
            # Первый approved пост → завтра в 10:00
            next_date = (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
        else:
            # Следующий пост → +1 день от последнего
            next_date = max_date + timedelta(days=1)

        # Обновить пост
        # Generate and save image if prompt exists
        image_url = None
        if post.get("image_prompt"):
            image_data = generate_image(post["image_prompt"])
            if image_data:
                image_path = os.path.join(UPLOAD_DIR, f"post_{post_id}.jpg")
                with open(image_path, "wb") as img_file:
                    img_file.write(image_data)
                image_url = image_path

        db.update_content_plan_entry(
            post_id=post_id,
            status="approved",
            publish_date=next_date.strftime("%Y-%m-%d %H:%M:%S"),
            image_url=image_url
        )

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
        drafts = db.get_draft_posts()
        post = next((p for p in drafts if p['id'] == post_id), None)

        # Удаляем пост
        db.delete_post(post_id)

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

# Подключаемся к БД
db.connect()

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
