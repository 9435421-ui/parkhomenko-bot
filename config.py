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

# === ADMIN GROUP ===
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "0"))

# Channel display information
CHANNEL_NAME = os.getenv("TARGET_CHANNEL_USERNAME", "@terion_channel")
_channel_username = CHANNEL_NAME.lstrip("@") if CHANNEL_NAME.startswith("@") else CHANNEL_NAME
CHANNEL_LINK = os.getenv("TARGET_CHANNEL_LINK", f"https://t.me/{_channel_username}")

def parse_channel_id(channel_id_str: str | None) -> int | str | None:
    """
    Эталонная функция для парсинга ID канала из строки.
    Поддерживает как числовой ID (например, -1001234567890), так и username (например, @channel_name).

    Args:
        channel_id_str: Строка с ID канала или username, может быть None или пустой строкой

    Returns:
        int если это числовой ID, str если это username (начинается с @), None если пустая строка или None

    Note:
        Функция не проверяет значение на 0 - если явно задан 0, значит так нужно для тестов или безопасности.
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

# Channel IDs for different purposes
CHANNEL_ID_STR = os.getenv("CHANNEL_ID")
CHANNEL_ID = parse_channel_id(CHANNEL_ID_STR) if CHANNEL_ID_STR else None

CONTENT_CHANNEL_ID_STR = os.getenv("CONTENT_CHANNEL_ID")
CONTENT_CHANNEL_ID = parse_channel_id(CONTENT_CHANNEL_ID_STR) if CONTENT_CHANNEL_ID_STR else None

NOTIFICATIONS_CHANNEL_ID_STR = os.getenv("NOTIFICATIONS_CHANNEL_ID")
NOTIFICATIONS_CHANNEL_ID = parse_channel_id(NOTIFICATIONS_CHANNEL_ID_STR) if NOTIFICATIONS_CHANNEL_ID_STR else None

THREAD_ID_KVARTIRY = int(os.getenv("THREAD_ID_KVARTIRY", "0"))
THREAD_ID_KOMMERCIA = int(os.getenv("THREAD_ID_KOMMERCIA", "0"))
THREAD_ID_DOMA = int(os.getenv("THREAD_ID_DOMA", "0"))

# Mini App URL
MINI_APP_URL = os.getenv("MINI_APP_URL", "https://t.me/Parkhovenko_i_kompaniya_bot")
