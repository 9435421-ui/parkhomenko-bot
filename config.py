"""
Конфигурация бота ТЕРИОН.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# === TELEGRAM ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CONTENT_BOT_TOKEN = os.getenv("CONTENT_BOT_TOKEN")
VK_API_TOKEN = os.getenv("VK_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")

# === ГРУППЫ И КАНАЛЫ ===
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_NAME = "@kapremont_channel"
CHANNEL_LINK = "https://t.me/kapremont_channel"

ADMIN_ID = os.getenv("ADMIN_ID")
ADMIN_GROUP_ID = os.getenv("ADMIN_GROUP_ID")
LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "-1003370698977"))

# === THREADS ===
THREAD_ID_LEADS = int(os.getenv("THREAD_ID_LEADS", "2"))
THREAD_ID_KVARTIRY = int(os.getenv("THREAD_ID_KVARTIRY", "2"))
THREAD_ID_KOMMERCIA = int(os.getenv("THREAD_ID_KOMMERCIA", "5"))
THREAD_ID_DOMA = int(os.getenv("THREAD_ID_DOMA", "8"))
THREAD_ID_DRAFTS = int(os.getenv("THREAD_ID_DRAFTS", "85"))
THREAD_ID_SEASONAL = int(os.getenv("THREAD_ID_SEASONAL", "87"))
THREAD_ID_LOGS = int(os.getenv("THREAD_ID_LOGS", "88"))

# === AIOGRAM ===
GROUP_ID = LEADS_GROUP_CHAT_ID

# === КАНАЛЫ КОНТЕНТА ===
TERION_CHANNEL_ID = int(os.getenv("TERION_CHANNEL_ID", "-1003612599428"))
DOM_GRAND_CHANNEL_ID = int(os.getenv("DOM_GRAND_CHANNEL_ID", "-1003777777777"))
