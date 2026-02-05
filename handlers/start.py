from aiogram import Router, F
from aiogram.types import Message, ContentType
from aiogram.fsm.context import FSMContext
from handlers.quiz import QuizOrder
from keyboards.main_menu import get_consent_keyboard, get_main_menu, get_contact_keyboard

router = Router()

@router.message(F.text.startswith("/start"))
async def handle_start(message: Message, state: FSMContext):
    await message.answer(
        "👋 Здравствуйте! Я Антон, ИИ-помощник эксперта Пархоменко Юлии Владимировны.\n\n"
        "Для продолжения работы необходимо ваше согласие на обработку персональных данных "
        "и ознакомление с условиями оферты.",
        reply_markup=get_consent_keyboard()
    )


@router.message(F.text == "✅ Согласен и хочу продолжить")
async def handle_consent(message: Message, state: FSMContext):
    await message.answer(
        "Спасибо! Чтобы я мог передать ваши данные эксперту, пожалуйста, поделитесь вашим контактом.",
        reply_markup=get_contact_keyboard()
    )


@router.message(F.contact)
async def handle_contact(message: Message, state: FSMContext):
    await state.update_data(phone=message.contact.phone_number)
    await message.answer(
        "✅ Контакт получен! Теперь вы можете оставить заявку или задать вопрос.",
        reply_markup=get_main_menu()
    )


@router.callback_query(F.data == "mode:quiz")
async def start_quiz_callback(callback: Message, state: FSMContext):
    await state.set_state(QuizOrder.city)
    await callback.message.answer("1️⃣ В каком городе находится ваш объект?")
    await callback.answer()


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: Message, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Выберите действие:", reply_markup=get_main_menu())
    await callback.answer()
