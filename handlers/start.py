"""
Главное меню - без лишних кнопок
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from keyboards.main_menu import get_consent_keyboard, get_main_menu
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
    """Старт - только приветствие + согласие"""
    await message.answer(
        GREETING_TEXT,
        reply_markup=get_consent_keyboard()
    )
    await state.set_state(QuizStates.greeting)


@router.message(F.text == "✅ Согласен и хочу продолжить")
async def handle_consent(message: Message, state: FSMContext):
    """Согласие - сразу начинаем квиз"""
    await message.answer(
        "🏙️ <b>1. В каком городе находится объект?</b>",
        parse_mode="HTML"
    )
    await state.set_state(QuizStates.city)
