from aiogram import Router, F
from aiogram.types import Message, ContentType, CallbackQuery
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from handlers.quiz import QuizOrder
from keyboards.main_menu import get_consent_keyboard, get_main_menu, get_contact_keyboard
from services.lead_service import send_contact_to_logs

router = Router()
router.message.filter(F.chat.type == ChatType.PRIVATE)

@router.message(F.text.startswith("/start"))
async def handle_start(message: Message, state: FSMContext):
    payload = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else "direct"
    await state.update_data(source=payload)

    await message.answer(
        "👋 Здравствуйте! Я Антон, ИИ-ассистент компании ТЕРИОН.\n\n"
        "Я помогу вам с услугами по согласованию перепланировок. "
        "Для продолжения работы необходимо ваше согласие на обработку персональных данных "
        "и ознакомление с условиями оферты.",
        reply_markup=get_consent_keyboard()
    )


@router.message(F.text == "✅ Согласен и хочу продолжить")
async def handle_consent(message: Message, state: FSMContext):
    await message.answer(
        "Спасибо! Чтобы я мог передать ваши данные эксперту ТЕРИОН, пожалуйста, поделитесь вашим контактом.",
        reply_markup=get_contact_keyboard()
    )


@router.message(F.contact)
async def handle_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    name = message.contact.first_name or message.from_user.first_name
    await state.update_data(phone=phone, name=name)

    # Отправка в лог-ветку для CRM
    await send_contact_to_logs(message.bot, message.from_user.id, name, phone)

    await message.answer(
        f"✅ {name}, контакт получен! Теперь вы можете оставить заявку или задать вопрос.",
        reply_markup=get_main_menu()
    )


@router.callback_query(F.data == "mode:quiz")
async def start_quiz_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(QuizOrder.city)
    await callback.message.answer("1️⃣ В каком городе находится ваш объект?")
    await callback.answer()


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Выберите действие:", reply_markup=get_main_menu())
    await callback.answer()
