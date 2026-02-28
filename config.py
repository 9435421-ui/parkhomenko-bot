import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CONTENT_BOT_TOKEN = os.getenv("CONTENT_BOT_TOKEN")
VK_API_TOKEN = os.getenv("VK_API_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")
LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "-1003370698977"))
CHANNEL_ID = os.getenv("CHANNEL_ID")
NOTIFICATIONS_CHANNEL_ID = os.getenv("NOTIFICATIONS_CHANNEL_ID")
THREAD_ID_KVARTIRY = int(os.getenv("THREAD_ID_KVARTIRY", "0"))
THREAD_ID_KOMMERCIA = int(os.getenv("THREAD_ID_KOMMERCIA", "0"))
THREAD_ID_DOMA = int(os.getenv("THREAD_ID_DOMA", "0"))
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
FOLDER_ID = os.getenv("FOLDER_ID")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# DATABASE_URL оставлен для обратной совместимости, но рекомендуется использовать DATABASE_PATH
DATABASE_URL = os.getenv("DATABASE_URL")
UPLOAD_PLANS_DIR = os.getenv("UPLOAD_PLANS_DIR")
UPLOAD_DIR = os.getenv("UPLOAD_DIR")
ADMIN_ID = int(os.getenv("ADMIN_ID", "223465437"))
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "0"))
MINI_APP_URL = os.getenv("MINI_APP_URL")

# Database path - используем DATABASE_PATH из .env, fallback на стандартный путь
DATABASE_PATH = os.getenv("DATABASE_PATH", "database/terion.db")

CHANNEL_NAME = "@kapremont_channel"
CHANNEL_LINK = "https://t.me/kapremont_channel"
