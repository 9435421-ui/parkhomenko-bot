import os
from dotenv import load_dotenv

load_dotenv()

# === ТОКЕНЫ БОТОВ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CONTENT_BOT_TOKEN = os.getenv("CONTENT_BOT_TOKEN")

# === ВК ИНТЕГРАЦИЯ ===
VK_TOKEN = os.getenv("VK_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")

# === ИДЕНТИФИКАТОРЫ ГРУПП И КАНАЛОВ ===
LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "-1003370698977"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003612599428"))
NOTIFICATIONS_CHANNEL_ID = int(os.getenv("NOTIFICATIONS_CHANNEL_ID", "-1003471218598"))

# === ТОПИКИ (THREADS) В ГРУППЕ ЛИДОВ ===
THREAD_ID_KVARTIRY = int(os.getenv("THREAD_ID_KVARTIRY", "2"))
THREAD_ID_KOMMERCIA = int(os.getenv("THREAD_ID_KOMMERCIA", "5"))
THREAD_ID_DOMA = int(os.getenv("THREAD_ID_DOMA", "8"))

# === ТОПИКИ КОНТЕНТ-АГЕНТА ===
THREAD_ID_DRAFTS = int(os.getenv("THREAD_ID_DRAFTS", "85"))
THREAD_ID_SEASONAL = int(os.getenv("THREAD_ID_SEASONAL", "87"))
THREAD_ID_LOGS = int(os.getenv("THREAD_ID_LOGS", "88"))

# === НЕЙРОСЕТИ (AI) ===
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
FOLDER_ID = os.getenv("FOLDER_ID")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
ROUTER_AI_KEY = os.getenv("ROUTER_AI_KEY")

# === TELEGRAM API (FOR SPY WORKER) ===
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")

# === БАЗА ДАННЫХ И ПУТИ ===
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///parkhomenko_bot.db")
UPLOAD_PLANS_DIR = os.getenv("UPLOAD_PLANS_DIR", "uploads_plans")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")

# === ПРОЧЕЕ ===
ADMIN_ID = int(os.getenv("ADMIN_ID", "223465437"))
MINI_APP_URL = os.getenv("MINI_APP_URL", "https://ternion.ru/mini_app/")

# Обратная совместимость (если нужно)
LEADS_GROUP_ID = LEADS_GROUP_CHAT_ID
