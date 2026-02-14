"""
Обработчик диалогового режима с RAG (консультант Антон)
Router AI (Kimi/Qwen) для ответов, YandexGPT как fallback
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from database import db
from utils import router_ai, yandex_gpt, kb
from keyboards import get_continue_or_menu_keyboard

router = Router()


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
    )
    await callback.answer()


@router.message(F.text)
async def dialog_message_handler(message: Message):
    """Обработка сообщений в диалоговом режиме"""
    user_id = message.from_user.id
    state = await db.get_user_state(user_id)
    
    # Проверяем, что пользователь в режиме диалога
    if not state or state.get('mode') != 'dialog':
        return
    
    user_query = message.text.strip()
    name = state.get('name', '')
    
    # Сохраняем сообщение пользователя в историю
    await db.add_dialog_message(user_id, role="user", message=user_query)
    
    # Получаем контекст из базы знаний через RAG
    rag_context = await kb.get_context(user_query, max_chunks=3, context_size=800)
    
    # Получаем историю диалога
    dialog_history = await db.get_dialog_history(user_id, limit=10)
    
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
            f"Я задам несколько вопросов, чтобы наш эксперт смог подготовить "
            f"предварительную консультацию.",
            parse_mode="HTML"
        )
        
        # Переходим к квизу
        from handlers.quiz import QuizOrder
        from aiogram.fsm.context import FSMContext
        from aiogram import Router
        from keyboards.main_menu import get_object_type_keyboard
        
        # Импортируем роутер quiz
        from handlers.quiz import router as quiz_router
        
        await message.answer(
            "📝 <b>Заявка на консультацию</b>\n\n"
            "<b>Вопрос 1 из 7:</b> В каком городе находится объект?",
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
        
        # После 2-го ответа предлагаем продолжить или оставить заявку
        assistant_count = len([h for h in history_for_prompt if h['role'] == 'assistant'])
        
        if assistant_count >= 2:
            await message.answer(
                f"{name}, хотите продолжить задавать вопросы или оставить заявку "
                f"для детальной консультации со специалистом ТЕРИОН?",
                reply_markup=get_continue_or_menu_keyboard()
            )
    
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
                "Попробуйте переформулировать вопрос или свяжитесь со специалистом.",
                reply_markup=get_continue_or_menu_keyboard()
            )
