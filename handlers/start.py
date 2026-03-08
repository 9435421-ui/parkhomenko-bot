"""
Обработчики команды /start и главного меню
aiogram 3.x версия
"""
from aiogram import Router, F, Dispatcher
from aiogram.types import Message, CallbackQuery, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart, CommandObject
from keyboards.main_menu import get_main_menu
from handlers.quiz import QuizOrder
from config import JULIA_USER_ID, ADMIN_ID, MINI_APP_URL

start_router = Router()


@start_router.message(F.text == "📝 Записаться на консультацию")
@start_router.callback_query(F.data == "mode:quiz")
async def start_quiz(message_or_callback: Message | CallbackQuery, state: FSMContext):
    """Запуск квиза при клике на кнопку или текстовом сообщении"""
    if isinstance(message_or_callback, CallbackQuery):
        message = message_or_callback.message
        await message_or_callback.answer()
    else:
        message = message_or_callback
    
    await state.clear()
    
    text = (
        "Вас приветствует компания ТЕРИОН!\n"
        "Я — Антон, ваш ИИ-помощник. Нажимая кнопку ниже, вы даете согласие на обработку персональных данных, "
        "получение уведомлений и информационную переписку.\n"
        "Все консультации носят информационный характер, финальное решение подтверждает эксперт ТЕРИОН."
    )
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить контакт и согласиться", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(text, reply_markup=keyboard)
    await state.set_state(QuizOrder.consent)


@start_router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    """Обработчик команды /start с поддержкой Deep Linking"""
    args = command.args
    user_id = message.from_user.id
    
    # Deep Linking: t.me/bot?start=quiz
    if args == "quiz":
        await state.clear()
        return await start_quiz(message, state)
    
    # Проверка на админа (Юлия или тех. админ)
    is_admin = user_id in [JULIA_USER_ID, ADMIN_ID]
    
    if is_admin:
        await message.answer(
            "👋 Здравствуйте, Юлия Владимировна! (Админ-панель)\n\n"
            "Выберите действие:",
            reply_markup=get_main_menu()
        )
    else:
        # Обычный пользователь: только одна кнопка
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📝 Записаться на консультацию")]
            ],
            resize_keyboard=True
        )
        
        await message.answer(
            "Вас приветствует компания ТЕРИОН! Я — Антон, ваш ИИ-помощник. "
            "Нажимая кнопку ниже, вы даете согласие на обработку персональных данных, "
            "получение уведомлений и информационную переписку.\n\n"
            "Задайте мне любой вопрос по вашей ситуации, и я постараюсь помочь!",
            reply_markup=keyboard
        )


def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков для aiogram 3.x"""
    dp.include_router(start_router)
