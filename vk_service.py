import os
import logging
from dotenv import load_dotenv
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id

# Import shared logic where possible
from llm_client import call_llm
from database import db

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VK_TOKEN = os.getenv("VK_TOKEN")
VK_GROUP_ID = os.getenv("VK_GROUP_ID")

class VKBot:
    def __init__(self, token):
        self.vk = vk_api.VkApi(token=token)
        self.longpoll = VkLongPoll(self.vk)
        self.api = self.vk.get_api()

    def send_message(self, user_id, text, keyboard=None):
        params = {
            "user_id": user_id,
            "message": text,
            "random_id": get_random_id(),
        }
        if keyboard:
            params["keyboard"] = keyboard.get_keyboard()

        self.api.messages.send(**params)

    def start(self):
        logger.info("🚀 VK Bot started...")
        for event in self.longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                self.handle_message(event)

    def handle_message(self, event):
        user_id = event.user_id
        text = event.text.lower()

        if text in ["начать", "start", "привет"]:
            self.send_welcome(user_id)
        elif "инвест" in text:
            self.send_message(user_id, "💰 Модуль инвест-оценки в ВК находится в разработке. Пожалуйста, воспользуйтесь нашим Telegram-ботом.")
        else:
            # Simple AI Consultation bridge
            response = call_llm("Ты - Антон, ИИ-консультант ЛАД: Согласование и Проектирование. Отвечай кратко.", text)
            self.send_message(user_id, response)

    def send_welcome(self, user_id):
        welcome_text = (
            "Привет! Я Антон, ИИ-консультант сервиса «ЛАД: Согласование и Проектирование». 🏠\n\n"
            "Я помогу вам узнать, законна ли ваша перепланировка и сколько она добавит к стоимости квартиры.\n\n"
            "Напишите свой вопрос или выберите раздел меню ниже."
        )
        self.send_message(user_id, welcome_text)

if __name__ == "__main__":
    if not VK_TOKEN:
        print("❌ VK_TOKEN not found in .env")
    else:
        bot = VKBot(VK_TOKEN)
        bot.start()
