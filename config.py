import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CONTENT_BOT_TOKEN = os.getenv("CONTENT_BOT_TOKEN")
VK_API_TOKEN = os.getenv("VK_API_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")
LEADS_GROUP_CHAT_ID = int(os.getenv("LEADS_GROUP_CHAT_ID", "-1003370698977"))

def parse_channel_id(channel_id_str: str) -> int | str | None:
    """
    Парсит ID канала из строки.
    Поддерживает как числовой ID (например, -1001234567890), так и username (например, @channel_name).
    
    Args:
        channel_id_str: Строка с ID канала или username
        
    Returns:
        int если это числовой ID, str если это username (начинается с @), None если пустая строка
    """
    if not channel_id_str:
        return None
    
    if channel_id_str.startswith("@"):
        # Если передан username канала (например, @channel_name), используем как строку
        return channel_id_str
    else:
        # Если передан числовой ID, конвертируем в int
        try:
            return int(channel_id_str)
        except ValueError:
            raise ValueError(
                f"Channel ID должен быть числовым ID (например, -1001234567890) "
                f"или username канала (например, @channel_name), получено: {channel_id_str}"
            )

CHANNEL_ID_STR = os.getenv("CHANNEL_ID")
CHANNEL_ID = parse_channel_id(CHANNEL_ID_STR) if CHANNEL_ID_STR else None

CONTENT_CHANNEL_ID_STR = os.getenv("CONTENT_CHANNEL_ID")
CONTENT_CHANNEL_ID = parse_channel_id(CONTENT_CHANNEL_ID_STR) if CONTENT_CHANNEL_ID_STR else None

NOTIFICATIONS_CHANNEL_ID_STR = os.getenv("NOTIFICATIONS_CHANNEL_ID")
NOTIFICATIONS_CHANNEL_ID = parse_channel_id(NOTIFICATIONS_CHANNEL_ID_STR) if NOTIFICATIONS_CHANNEL_ID_STR else None
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
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "0"))
MINI_APP_URL = os.getenv("MINI_APP_URL")
JULIA_USER_ID = int(os.getenv("JULIA_USER_ID", "0"))
JULIA_CONTACT = os.getenv("JULIA_CONTACT", "@terion_expert")
THREAD_ID_LOGS = int(os.getenv("THREAD_ID_LOGS", "88"))
THREAD_ID_DRAFTS = int(os.getenv("THREAD_ID_DRAFTS", "85"))
VK_QUIZ_LINK = os.getenv("VK_QUIZ_LINK", "https://vk.com/app123456")
CONTENT_HASHTAGS = os.getenv("CONTENT_HASHTAGS", "#перепланировка #москва")

# Database path - используем DATABASE_PATH из .env, fallback на стандартный путь
DATABASE_PATH = os.getenv("DATABASE_PATH", "database/terion.db")

CHANNEL_NAME = "@kapremont_channel"
CHANNEL_LINK = "https://t.me/kapremont_channel"
