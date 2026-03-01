"""
Обработчики команды /start и главного меню
aiogram 3.x версия
"""
from aiogram import Router, F, Dispatcher
from aiogram.types import Message, CallbackQuery, WebAppInfo
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart, CommandObject
from keyboards.main_menu import get_main_menu
from handlers.quiz import QuizOrder
from config import JULIA_USER_ID, ADMIN_ID, MINI_APP_URL

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
        "В каком городе находится объект?"
    )


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    """Обработчик команды /start с поддержкой Deep Linking"""
    args = command.args
    user_id = message.from_user.id
    
    # Deep Linking: t.me/bot?start=quiz
    if args == "quiz":
        await state.clear()
        await state.set_state(QuizOrder.city)
        return await message.answer(
            "📝 Начинаем опрос для подготовки анализа вашей ситуации.\n\n"
            "В каком городе находится объект?"
        )
    
    # Deep Linking: t.me/bot?start=calc
    if args == "calc":
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="💰 Открыть калькулятор", web_app=WebAppInfo(url=MINI_APP_URL))
        return await message.answer(
            "💰 Инвест-калькулятор готов к работе!",
            reply_markup=builder.as_markup()
        )

    # Проверка на админа (Юлия или тех. админ)
    is_admin = user_id in [JULIA_USER_ID, ADMIN_ID]
    
    if is_admin:
        await message.answer(
            "👋 Здравствуйте, Юлия Владимировна! (Админ-панель)\n\n"
            "Выберите действие:",
            reply_markup=get_main_menu()
        )
    else:
        await message.answer(
            "👋 Здравствуйте! Я Антон, ИИ-помощник эксперта "
            "Пархоменко Юлии Владимировны по согласованию перепланировок.\n\n"
            "Задайте мне любой вопрос по вашей ситуации, и я постараюсь помочь!"
        )


def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков для aiogram 3.x"""
    dp.include_router(router)
