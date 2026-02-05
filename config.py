import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
ADMIN_GROUP_ID = os.getenv("ADMIN_GROUP_ID", "твой_id")

YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID", "")

CHANNEL_NAME = "@kapremont_channel"
CHANNEL_LINK = "https://t.me/kapremont_channel"
