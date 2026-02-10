"""
Конфигурация ботов, каналов и топиков.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# === TELEGRAM BOT TOKENS ===
BOT_TOKEN = os.getenv("BOT_TOKEN")  # ТЕРИОН (Антон)
CONTENT_BOT_TOKEN = os.getenv("CONTENT_BOT_TOKEN")  # ДОМ ГРАНД (Контент)

# === VK ===
VK_TOKEN = os.getenv("VK_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")

# === CHANNELS (ПУБЛИКАЦИЯ) ===
CHANNEL_ID_TERION = int(os.getenv("CHANNEL_ID_TERION", "-1003612599428"))
CHANNEL_ID_DOM_GRAD = int(os.getenv("CHANNEL_ID_DOM_GRAD", "-1002628548032"))
NOTIFICATIONS_CHANNEL_ID = int(os.getenv("NOTIFICATIONS_CHANNEL_ID", "-1003471218598"))

# === WORKING GROUP (ОБСУЖДЕНИЕ) ===
LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "-1003370698977"))

# === THREADS IN WORKING GROUP ===
THREAD_ID_KVARTIRY = int(os.getenv("THREAD_ID_KVARTIRY", "2"))
THREAD_ID_KOMMERCIA = int(os.getenv("THREAD_ID_KOMMERCIA", "5"))
THREAD_ID_DOMA = int(os.getenv("THREAD_ID_DOMA", "8"))
THREAD_ID_NEWS = int(os.getenv("THREAD_ID_NEWS", "780"))          # Новости
THREAD_ID_CONTENT_PLAN = int(os.getenv("THREAD_ID_CONTENT_PLAN", "83"))  # Контент план
THREAD_ID_DRAFTS = int(os.getenv("THREAD_ID_DRAFTS", "85"))       # Черновики
THREAD_ID_TRENDS_SEASON = int(os.getenv("THREAD_ID_TRENDS_SEASON", "87"))  # Тренды/Сезонное
THREAD_ID_LOGS = int(os.getenv("THREAD_ID_LOGS", "88"))           # Логи системы

# === AI ===
ROUTER_AI_KEY = os.getenv("ROUTER_AI_KEY")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
FOLDER_ID = os.getenv("FOLDER_ID")

# === ADMIN ===
ADMIN_ID = int(os.getenv("ADMIN_ID", "223465437"))
QUIZ_THREAD_ID = int(os.getenv("QUIZ_THREAD_ID", "2"))
THREAD_ID_HOT_LEADS = int(os.getenv("THREAD_ID_HOT_LEADS", "10"))

# === PATHS ===
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///parkhomenko_bot.db")
UPLOAD_PLANS_DIR = os.getenv("UPLOAD_PLANS_DIR", "uploads_plans")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
MINI_APP_URL = os.getenv("MINI_APP_URL", "https://ternion.ru/mini_app/")

# === FEATURES ===
ENABLE_IMAGE_GENERATION = os.getenv("ENABLE_IMAGE_GENERATION", "false").lower() == "true"
COMPETITOR_SPY_ENABLED = os.getenv("COMPETITOR_SPY_ENABLED", "false").lower() == "true"
GEO_SPY_ENABLED = os.getenv("GEO_SPY_ENABLED", "false").lower() == "true"
