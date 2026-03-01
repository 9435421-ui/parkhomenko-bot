"""
Обработчик диалогового режима консультаций
"""
from aiogram import Router
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

dialog_router = Router()


from aiogram import F
from aiogram.types import CallbackQuery
from utils.yandex_gpt import yandex_gpt
from utils.knowledge_base import kb
from database.db import db

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
    """
    Обработчик диалогового режима консультаций с использованием RAG и YandexGPT
    """
    user_id = message.from_user.id
    user_state = await db.get_user_state(user_id)
    
    # Проверяем, находится ли пользователь в режиме диалога
    if not user_state or user_state.get("mode") != "dialog":
        return

    # Поиск контекста в базе знаний
    context = await kb.get_context(message.text)
    
    # Получаем историю диалога
    history = await db.get_dialog_history(user_id)
    
    # Генерация ответа через специализированный метод
    response_text = await yandex_gpt.generate_with_context(
        user_query=message.text,
        rag_context=context,
        dialog_history=history,
        user_name=message.from_user.first_name
    )
    
    # Сохранение в историю
    await db.add_dialog_message(user_id, "user", message.text)
    await db.add_dialog_message(user_id, "assistant", response_text)
    
    await message.answer(response_text)


# Экспорт router для совместимости с handlers/__init__.py
router = dialog_router
