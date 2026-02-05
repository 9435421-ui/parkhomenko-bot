from aiogram import Router, F
from aiogram.types import Message
from config import NOTIFICATIONS_CHANNEL_ID

router = Router()

KEYWORDS = ["перепланировка", "снос стены", "узаконить", "бти", "согласование"]

@router.message(F.chat.type.in_({"group", "supergroup"}))
async def monitor_keywords(message: Message):
    if not message.text:
        return

    text_lower = message.text.lower()
    if any(word in text_lower for word in KEYWORDS):
        alert = (
            f"🕵️‍♂️ <b>ОБНАРУЖЕНО КЛЮЧЕВОЕ СЛОВО</b>\n\n"
            f"Чат: {message.chat.title}\n"
            f"Пользователь: @{message.from_user.username or message.from_user.id}\n"
            f"Сообщение: {message.text}\n"
            f"Ссылка: {message.get_url()}"
        )

        await message.bot.send_message(
            chat_id=NOTIFICATIONS_CHANNEL_ID,
            text=alert,
            parse_mode="HTML"
        )
