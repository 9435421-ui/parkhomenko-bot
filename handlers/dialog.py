"""
Обработчик диалогового режима консультаций
aiogram 3.x версия
"""
from aiogram import Router, F, Dispatcher
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from utils.yandex_gpt import yandex_gpt
from utils.knowledge_base import kb
from database.db import db

dialog_router = Router()


@dialog_router.callback_query(F.data == "mode:dialog")
async def start_dialog_mode(callback: CallbackQuery, state: FSMContext):
    """Переход в режим диалога"""
    await state.clear()
    await db.update_user_state(callback.from_user.id, mode="dialog")
    await callback.message.answer(
        "💬 Вы перешли в режим диалога с ИИ-консультантом.\n"
        "Задайте любой вопрос по перепланировке, и я постараюсь помочь!"
    )
    await callback.answer()


@dialog_router.message()
async def dialog_handler(message: Message, state: FSMContext):
    """Обработчик диалогового режима"""
    user_id = message.from_user.id
    user_state = await db.get_user_state(user_id)
    
    if not user_state or user_state.get("mode") != "dialog":
        return
    
    context = await kb.get_context(message.text)
    history = await db.get_dialog_history(user_id)
    
    response_text = await yandex_gpt.generate_with_context(
        user_query=message.text,
        rag_context=context,
        dialog_history=history,
        user_name=message.from_user.first_name
    )
    
    await db.add_dialog_message(user_id, "user", message.text)
    await db.add_dialog_message(user_id, "assistant", response_text)
    
    await message.answer(response_text)


def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков диалога"""
    dp.include_router(dialog_router)
