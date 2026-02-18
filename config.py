"""
Конфигурация ботов, каналов и топиков.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# === TELEGRAM BOT TOKENS ===
BOT_TOKEN = os.getenv("BOT_TOKEN")  # ТЕРИОН (Антон)
CONTENT_BOT_TOKEN = os.getenv("CONTENT_BOT_TOKEN")  # ДОМ ГРАНД

# === TELETHON CREDENTIALS (for Chat Parsing) ===
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
PHONE = os.getenv("PHONE")

# === VK ===
VK_TOKEN = os.getenv("VK_TOKEN")
VK_GROUP_ID = int(os.getenv("VK_GROUP_ID", "235569022"))

# === CHANNELS (ПУБЛИКАЦИЯ) ===
CHANNEL_ID_TERION = int(os.getenv("CHANNEL_ID_TERION", "-1003612599428"))
CHANNEL_ID_DOM_GRAD = int(os.getenv("CHANNEL_ID_DOM_GRAD", "-1002628548032"))
NOTIFICATIONS_CHANNEL_ID = int(os.getenv("NOTIFICATIONS_CHANNEL_ID", "-1003471218598"))

# === CHANNEL NAMES ===
CHANNEL_NAMES = {
    "terion": "TERION",
    "dom_grand": "ДОМ ГРАНД"
}

# === WORKING GROUP (ОБСУЖДЕНИЕ) ===
LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "-1003370698977"))

# === КОНТЕНТ-ПЛАН: ВРЕМЯ И ЛИМИТЫ (для будущего использования) ===
# Время публикации по умолчанию (при сохранении поста без явной даты)
PUBLISH_TIME_DEFAULT = os.getenv("PUBLISH_TIME_DEFAULT", "12:00")  # МСК, "ЧЧ:ММ"
# Максимум постов в день в один канал (0 = без лимита)
POSTS_PER_DAY_LIMIT = int(os.getenv("POSTS_PER_DAY_LIMIT", "0"))

# === QUIZ LINK И ХЭШТЕГИ ДЛЯ ПОСТОВ ===
VK_QUIZ_LINK = os.getenv("VK_QUIZ_LINK", "https://t.me/TERION_KvizBot?start=quiz")
# Обязательные хэштеги в каждом посте (можно переопределить в .env)
CONTENT_HASHTAGS = os.getenv("CONTENT_HASHTAGS", "#TERION #перепланировка #недвижимость #москва")

# === THREADS IN WORKING GROUP ===
THREAD_ID_KVARTIRY = int(os.getenv("THREAD_ID_KVARTIRY", "2"))
THREAD_ID_KOMMERCIA = int(os.getenv("THREAD_ID_KOMMERCIA", "5"))
THREAD_ID_DOMA = int(os.getenv("THREAD_ID_DOMA", "8"))
THREAD_ID_NEWS = int(os.getenv("THREAD_ID_NEWS", "780"))          # Новости
THREAD_ID_CONTENT_PLAN = int(os.getenv("THREAD_ID_CONTENT_PLAN", "83"))  # Контент план
THREAD_ID_DRAFTS = int(os.getenv("THREAD_ID_DRAFTS", "85"))       # Черновики
THREAD_ID_TRENDS_SEASON = int(os.getenv("THREAD_ID_TRENDS_SEASON", "87"))  # Тренды/Сезонное
THREAD_ID_LOGS = int(os.getenv("THREAD_ID_LOGS", "88"))           # Логи системы

# === AI (разделение по назначению) ===
# Яндекс: персональные данные, хранение, законодательство РФ, акты. Опционально Яндекс АРТ для картинок.
# Router AI: одного ключа достаточно — логика ответов в чате и генерация изображений (Nano Banana / DALL-E).
ROUTER_AI_KEY = os.getenv("ROUTER_AI_KEY")
ROUTER_AI_ENDPOINT = os.getenv("ROUTER_AI_ENDPOINT", "https://routerai.ru/api/v1/chat/completions")
ROUTER_AI_CHAT_MODEL = os.getenv("ROUTER_AI_CHAT_MODEL", "gpt-4o-mini")  # логика чата: gpt-4o-mini / nano / kimi
ROUTER_AI_CHAT_FALLBACK = os.getenv("ROUTER_AI_CHAT_FALLBACK", "qwen")
ROUTER_AI_IMAGE_KEY = os.getenv("ROUTER_AI_IMAGE_KEY") or ROUTER_AI_KEY  # опционально отдельный ключ для генерации изображений
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
FOLDER_ID = os.getenv("FOLDER_ID")
MAX_API_KEY = os.getenv("MAX_API_KEY")
# MAX.ru канал: Device Token из приложения MAX (для API публикации)
MAX_DEVICE_TOKEN = os.getenv("MAX_DEVICE_TOKEN")
MAX_SUBSITE_ID = os.getenv("MAX_SUBSITE_ID")  # опционально: id канала, если не брать из API /subsite/me
YANDEX_ART_ENABLED = os.getenv("YANDEX_ART_ENABLED", "true").lower() == "true"
# Умный Охотник v2.0: агенты Yandex AI Studio (нормативная база в студии)
YANDEX_AI_AGENT_SPY_ID = os.getenv("YANDEX_AI_AGENT_SPY_ID", "fvt2vnpq2qjdt829em50")
YANDEX_AI_AGENT_ANTON_ID = os.getenv("YANDEX_AI_AGENT_ANTON_ID", "fvtrdfvmv1u84s9rfn5a")
YANDEX_AI_AGENTS_ENDPOINT = os.getenv("YANDEX_AI_AGENTS_ENDPOINT")  # опционально: URL вызова агента по ID
# Контакт Юлии для кнопки «Взять в работу»
JULIA_CONTACT = os.getenv("JULIA_CONTACT", "Юлия Пархоменко — эксперт по перепланировкам. Связь: @Parkhovenko_i_kompaniya_bot")
TERION_CHANNEL_ID = CHANNEL_ID_TERION
DOM_GRAND_CHANNEL_ID = CHANNEL_ID_DOM_GRAD
# === ADMIN ===
ADMIN_ID = int(os.getenv("ADMIN_ID", "223465437"))
# Юлия: полный доступ к /stats, /hunt и админ-меню
JULIA_USER_ID = int(os.getenv("JULIA_USER_ID", "8438024806"))


def is_admin(user_id: int) -> bool:
    """Доступ к админ-меню, /stats, /hunt: админ или Юлия."""
    return user_id == ADMIN_ID or (JULIA_USER_ID and user_id == JULIA_USER_ID)
QUIZ_THREAD_ID = int(os.getenv("QUIZ_THREAD_ID", "2"))
THREAD_ID_HOT_LEADS = int(os.getenv("THREAD_ID_HOT_LEADS", "811"))  # топик «Горячие лиды» в рабочей группе

# === PATHS ===
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///parkhomenko_bot.db")
UPLOAD_PLANS_DIR = os.getenv("UPLOAD_PLANS_DIR", "uploads_plans")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
MINI_APP_URL = os.getenv("MINI_APP_URL", "https://ternion.ru/mini_app/")

# === FEATURES ===
ENABLE_IMAGE_GENERATION = os.getenv("ENABLE_IMAGE_GENERATION", "true").lower() == "true"
COMPETITOR_SPY_ENABLED = os.getenv("COMPETITOR_SPY_ENABLED", "false").lower() == "true"
GEO_SPY_ENABLED = os.getenv("GEO_SPY_ENABLED", "true").lower() == "true"  # Шпион включен

# === GEO CHATS (Шпион) ===
GEO_CHAT_ID = os.getenv("GEO_CHAT_ID", "-1001234567890")
GEO_CHAT_1_ID = os.getenv("GEO_CHAT_1_ID", "-1001987654321")

# === KEYWORDS FOR SPY ===
SPY_KEYWORDS = [
    "перепланировка",
    "проем",
    "нежилое",
    "согласование",
    "узаконить",
    "перевод",
    "документы",
    "МЖИ",
    "снос стены",
    "объединение",
    "ремонт",
    "дизайн",
    "Пархоменко",
    "Терион",
]

# === SCOUT PARSER ===
SCOUT_ENABLED = os.getenv("SCOUT_ENABLED", "true") == "true"

# Telegram
SCOUT_TG_CHANNELS = os.getenv("SCOUT_TG_CHANNELS", "").split(",")
SCOUT_TG_KEYWORDS = ["перепланировка", "согласование", "узаконить"]

# VK
SCOUT_VK_GROUPS = os.getenv("SCOUT_VK_GROUPS", "").split(",")  # ID групп
SCOUT_VK_KEYWORDS = ["перепланировка", "согласование", "перепланировка квартиры", "узаконить перепланировку"]
SCOUT_VK_REGIONS = ["Химки", "Красногорск", "Север Москвы", "Северо-Запад Москвы", "Новые Химки"]

# Лимиты (чтобы не забанили)
SCOUT_VK_COMMENTS_PER_HOUR = 5  # Макс комментариев в час
SCOUT_VK_MESSAGES_PER_HOUR = 3  # Макс
