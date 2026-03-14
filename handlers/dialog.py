"""
<<<<<<< HEAD
Обработчик диалогового режима консультаций
aiogram 3.x версия
=======
Диалог с консультантом Антоном (RAG).
Логика ответов: Router AI (GPT-4 nano / Kimi). Контекст из базы знаний (законодательство РФ).
Fallback: YandexGPT (персональные данные, РФ акты — см. общую схему AI в config).
Сообщения в режиме квиза не обрабатываем — их должен обрабатывать только quiz_router.
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
"""
from aiogram import Router, F, Dispatcher
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
<<<<<<< HEAD
=======
from aiogram.filters import StateFilter
from database import db
from utils import router_ai, yandex_gpt, kb
from handlers.quiz import QuizStates
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377

from utils.yandex_gpt import yandex_gpt
from utils.knowledge_base import kb
from database.db import db

dialog_router = Router()


<<<<<<< HEAD
@dialog_router.callback_query(F.data == "mode:dialog")
async def start_dialog_mode(callback: CallbackQuery, state: FSMContext):
    """Переход в режим диалога"""
    await state.clear()
    await db.update_user_state(callback.from_user.id, mode="dialog")
    await callback.message.answer(
        "💬 Вы перешли в режим диалога с ИИ-консультантом.\n"
        "Задайте любой вопрос по перепланировке, и я постараюсь помочь!"
=======
@router.callback_query(F.data == "mode:dialog")
async def start_dialog(callback: CallbackQuery):
    """Запуск диалогового режима"""
    user_id = callback.from_user.id
    
    # Устанавливаем режим диалога
    await db.update_user_state(user_id, mode="dialog")
    
    state = await db.get_user_state(user_id)
    name = state.get('name', 'дорогой клиент')
    
    await callback.message.edit_text(
        f"💬 <b>Консультация с Антоном</b>\n\n"
        f"{name}, я — ИИ-консультант компании ТЕРИОН по перепланировкам. "
        f"Отвечу на ваши вопросы, опираясь на базу знаний из 83 документов "
        f"по законодательству РФ и практическому опыту.\n\n"
        f"<b>Опишите вашу ситуацию или задайте конкретный вопрос.</b>",
        parse_mode="HTML"
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
    )
    await callback.answer()


<<<<<<< HEAD
@dialog_router.message()
async def dialog_handler(message: Message, state: FSMContext):
    """Обработчик диалогового режима"""
    user_id = message.from_user.id
    user_state = await db.get_user_state(user_id)
    
    if not user_state or user_state.get("mode") != "dialog":
        return
    
    context = await kb.get_context(message.text)
    history = await db.get_dialog_history(user_id)
=======
@router.message(F.text, ~StateFilter(QuizStates))
async def dialog_message_handler(message: Message, state: FSMContext):
    """Обработка сообщений в диалоговом режиме. Не срабатывает в состоянии квиза — тогда отвечает quiz."""
    user_id = message.from_user.id
    user_state = await db.get_user_state(user_id)
    
    # Проверяем, что пользователь в режиме диалога
    if not user_state or user_state.get('mode') != 'dialog':
        print(f"DEBUG: User {user_id} not in dialog mode, ignoring")
        return
    
    user_query = message.text.strip()
    name = user_state.get('name', '')
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
    
    response_text = await yandex_gpt.generate_with_context(
        user_query=message.text,
        rag_context=context,
        dialog_history=history,
        user_name=message.from_user.first_name
    )
    
    # Добавляем CTA (Call to Action)
    response_text += "\n\n---\n📝 Чтобы получить точный расчет и бесплатную консультацию, нажмите /start и выберите «Оставить заявку»."
    
    await db.add_dialog_message(user_id, "user", message.text)
    await db.add_dialog_message(user_id, "assistant", response_text)
    
<<<<<<< HEAD
    await message.answer(response_text)


def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков диалога"""
    dp.include_router(dialog_router)
=======
    # Формируем историю для промпта
    history_for_prompt = []
    for msg in dialog_history:
        history_for_prompt.append({
            'role': msg['role'],
            'text': msg['message']
        })
    
    # Проверка на триггер-слова (связь со специалистом)
    trigger_words = [
        'специалист', 'менеджер', 'человек', 'живой', 'соединить',
        'связаться', 'заказать', 'консультация', 'записаться'
    ]
    
    if any(word in user_query.lower() for word in trigger_words):
        await db.update_user_state(user_id, mode="quiz", quiz_step=1)
        
        await message.answer(
            f"{name}, отлично! Давайте оформим заявку для связи со специалистом.\n\n"
            f"🏙️ <b>1. В каком городе находится объект?</b>",
            parse_mode="HTML"
        )
        return
    
    # Генерируем ответ через Router AI (Kimi/Qwen) с RAG
    try:
        response = await router_ai.generate_with_context(
            user_query=user_query,
            rag_context=rag_context,
            dialog_history=history_for_prompt,
            user_name=name,
            consultant_style=True
        )
        
        # Сохраняем ответ в историю
        await db.add_dialog_message(user_id, role="assistant", message=response)
        
        # Отправляем ответ пользователю
        await message.answer(response, parse_mode="HTML")
    
    except Exception as e:
        print(f"❌ Ошибка Router AI: {e}")
        
        # Fallback на YandexGPT
        try:
            response = await yandex_gpt.generate_with_context(
                user_query=user_query,
                rag_context=rag_context,
                dialog_history=history_for_prompt,
                user_name=name
            )
            
            await db.add_dialog_message(user_id, role="assistant", message=response)
            await message.answer(response, parse_mode="HTML")
            
        except Exception as yandex_error:
            print(f"❌ Ошибка YandexGPT fallback: {yandex_error}")
            await message.answer(
                "Извините, произошла техническая ошибка. "
                "Попробуйте переформулировать вопрос."
            )
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
