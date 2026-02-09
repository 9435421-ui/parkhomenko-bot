"""
Главное меню - захват контакта в начале
"""
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from keyboards.main_menu import get_contact_keyboard
from handlers.quiz import QuizStates

router = Router()

GREETING_TEXT = (
    "🏢 <b>Вас приветствует компания ТЕРИОН!</b>\n\n"
    "Я — Антон, ваш ИИ-помощник по перепланировкам.\n\n"
    "Нажимая кнопку ниже, вы даете согласие на обработку "
    "персональных данных, получение уведомлений и информационную переписку.\n\n"
    "📞 Все консультации носят информационный характер, "
    "финальное решение подтверждает эксперт ТЕРИОН."
)


@router.message(F.text.startswith("/start"))
async def handle_start(message: Message, state: FSMContext):
    """Старт - приветствие + кнопка контакта"""
    await message.answer(
        GREETING_TEXT,
        reply_markup=get_contact_keyboard()
    )
    await state.set_state(QuizStates.contact)


@router.message(F.contact)
async def process_contact(message: Message, state: FSMContext):
    """Ловим контакт - сохраняем и переходим к вопросам"""
    user_name = message.from_user.full_name or message.from_user.first_name or "Клиент"
    phone = message.contact.phone_number
    
    # Сохраняем в state
    await state.update_data(user_name=user_name, phone=phone)
    
    # Убираем кнопку контакта
    await message.answer(
        f"✅ {user_name}, приятно познакомиться!\n"
        f"Телефон {phone} получен.\n\n"
        "Для первичного анализа вашего объекта ответьте на несколько вопросов:",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Первый вопрос
    await message.answer(
        "🏙️ <b>1. В каком городе находится объект?</b>",
        parse_mode="HTML"
    )
    await state.set_state(QuizStates.city)


@router.message(F.text)
async def ignore_text(message: Message):
    """Игнорируем текстовые сообщения пока не получен контакт"""
    await message.answer(
        "📱 <b>Пожалуйста, нажмите кнопку ниже</b>\n\n"
        "«📱 Отправить контакт и согласиться»",
        reply_markup=get_contact_keyboard()
    )
