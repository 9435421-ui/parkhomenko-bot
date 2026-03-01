"""
Обработчики команды /start и главного меню
aiogram 2.x версия
"""
from aiogram import Dispatcher, types
from keyboards.main_menu import get_main_menu
from handlers.quiz import QuizOrder


def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков для aiogram 2.x"""
    
    @dp.message_handler(text="📝 Записаться на консультацию")
    @dp.callback_query_handler(lambda c: c.data == "mode:quiz")
    async def start_quiz(message_or_callback: types.Message | types.CallbackQuery, state):
        """Запуск квиза при клике на кнопку или текстовом сообщении"""
        if isinstance(message_or_callback, types.CallbackQuery):
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
    
    @dp.message_handler(commands=["start"])
    async def cmd_start(message: types.Message):
        """Обработчик команды /start"""
        await message.answer(
            "👋 Здравствуйте! Я Антон, ИИ-помощник эксперта "
            "Пархоменко Юлии Владимировны по согласованию перепланировок.\n\n"
            "Выберите действие:",
            reply_markup=get_main_menu()
        )
