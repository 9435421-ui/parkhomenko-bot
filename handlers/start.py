"""
Главное меню - старт квиза
"""
from aiogram import Router, F
from aiogram.types import Message
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
    """Старт - показываем приветствие + кнопка контакта"""
    await state.clear()  # Очищаем старые состояния
    await message.answer(
        GREETING_TEXT,
        reply_markup=get_contact_keyboard()
    )
    await state.set_state(QuizStates.greeting)
