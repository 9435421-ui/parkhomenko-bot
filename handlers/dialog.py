"""
Обработчик диалогового режима (консультант Антон)
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from database.db import db
from keyboards.main_menu import get_continue_or_menu_keyboard

router = Router()

@router.callback_query(F.data == "mode:dialog")
async def start_dialog(callback: CallbackQuery):
    """Запуск диалогового режима"""
    user_id = callback.from_user.id
    
    await db.update_user_state(user_id, mode="dialog")
    state = await db.get_user_state(user_id)
    name = state.get('name', 'дорогой клиент') if state else 'дорогой клиент'
    
    await callback.message.edit_text(
        f"💬 <b>Консультация с Антоном</b>\n\n"
        f"{name}, я - ИИ-ассистент компании ТЕРИОН. "
        f"Готов ответить на ваши вопросы по перепланировкам.\n\n"
        f"<b>Опишите вашу ситуацию или задайте конкретный вопрос.</b>",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(F.text)
async def dialog_message_handler(message: Message):
    """Заглушка для диалога (в реальном проекте здесь RAG)"""
    user_id = message.from_user.id
    state = await db.get_user_state(user_id)
    
    if not state or state.get('mode') != 'dialog':
        return
    
    # Здесь должна быть логика YandexGPT, но для стабилизации оставим простой ответ
    # или предложение перейти к квизу.
    
    await message.answer(
        "Я получил ваш вопрос! Для точного ответа мне нужно изучить детали вашего объекта. "
        "Давайте заполним небольшую анкету?",
        reply_markup=get_continue_or_menu_keyboard()
    )
