"""
Обработчики команды /start и главного меню
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from keyboards.main_menu import get_main_menu
from handlers.quiz import QuizOrder

router = Router()


@router.message(F.text == "📝 Записаться на консультацию")
@router.callback_query(F.data == "mode:quiz")
async def start_quiz(message_or_callback: Message | CallbackQuery, state: FSMContext):
    """Запуск квиза при клике на кнопку или текстовом сообщении"""
    if isinstance(message_or_callback, CallbackQuery):
        message = message_or_callback.message
        await message_or_callback.answer()
    else:
        message = message_or_callback
    
    await state.set_state(QuizOrder.city)
    await message.answer(
        "📝 Отлично! Давайте соберем информацию для заявки.\n\n"
        "В каком городе находится объект?",
        reply_markup=get_main_menu()
    )


@router.message(F.text == "/start")
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    await message.answer(
        "👋 Здравствуйте! Я Антон, ИИ-помощник эксперта "
        "Пархоменко Юлии Владимировны по согласованию перепланировок.\n\n"
        "Выберите действие:",
        reply_markup=get_main_menu()
    )
