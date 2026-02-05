from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import THREAD_ID_DRAFTS, OPENROUTER_API_KEY, CHANNEL_ID
from services.vk_service import vk_service
import aiohttp

router = Router()

@router.message(F.message_thread_id == THREAD_ID_DRAFTS)
async def handle_interview(message: Message):
    if not message.text or message.text.startswith("/"):
        return

    facts = message.text
    await message.answer("🤖 Генерирую черновик...")

    prompt = f"Напиши пост для Telegram на основе фактов: {facts}. Стиль: экспертный."

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            json={"model": "openai/gpt-3.5-turbo", "messages": [{"role": "user", "content": prompt}]}
        ) as resp:
            result = await resp.json()
            draft = result['choices'][0]['message']['content']

            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📢 В Telegram", callback_data="post:tg")],
                [InlineKeyboardButton(text="💙 В VK", callback_data="post:vk")]
            ])
            await message.answer(f"📝 <b>Черновик:</b>\n\n{draft}", parse_mode="HTML", reply_markup=markup)

@router.callback_query(F.data.startswith("post:"))
async def handle_post(callback: CallbackQuery):
    text = callback.message.text.split("Черновик:\n\n")[-1]

    if callback.data == "post:tg":
        await callback.bot.send_message(chat_id=CHANNEL_ID, text=text)
        await callback.answer("✅ Опубликовано в Telegram")
    elif callback.data == "post:vk":
        success = await vk_service.send_to_community(message=text)
        await callback.answer("✅ Опубликовано в VK" if success else "❌ Ошибка VK")
