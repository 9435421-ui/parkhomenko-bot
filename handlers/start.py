from aiogram import Router, F
from aiogram.types import Message, ContentType
from aiogram.fsm.context import FSMContext
from handlers.quiz import QuizOrder
from keyboards.main_menu import get_consent_keyboard, get_main_menu
from config import LEADS_GROUP_CHAT_ID

router = Router()

@router.message(F.text.startswith("/start"))
async def handle_start(message: Message, state: FSMContext):
    payload = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    await state.set_state(QuizOrder.city)
    await message.answer(
        "Прежде чем мы начнем, я должен сообщить: я, Антон — цифровой помощник эксперта Юлии Пархоменко. "
        "Нажимая кнопку \"Начать\", вы даете согласие на обработку персональных данных и принимаете условия политики конфиденциальности, "
        "а также на отправку вам информационных сообщений и переписку.\n\n"
        "Все мои консультации носят информационный характер, финальное решение всегда подтверждает эксперт, Юлия Пархоменко.",
        reply_markup=get_consent_keyboard()
    )
    await state.update_data(_payload=payload)


@router.message(F.text == "✅ Согласен и хочу продолжить")
async def handle_consent(message: Message, state: FSMContext):
    """Обработка согласия пользователя"""
    data = await state.get_data()
    payload = data.get('_payload', '')

    if payload == 'quiz':
        # Запрос контакта перед началом квиза
        await message.answer(
            "Для начала квиза мне нужен ваш контакт. Пожалуйста, поделитесь вашим номером телефона.",
            reply_markup=message.bot.get_contact_request_button("Поделиться номером")
        )
    elif payload == 'invest':
        # Запуск инвестиционного калькулятора
        await state.set_state(QuizOrder.city)
        await message.answer("💰 Давайте оценим капитализацию вашего объекта после перепланировки. Какой город?")
    elif payload == 'expert':
        # Запуск экспертизы
        await state.set_state(QuizOrder.city)
        await message.answer("🔍 Какой тип недвижимости? (Жилая/Коммерческая/Инвестиционная)")
        await message.answer("❓ Есть ли ипотека/банк на объекте?")
    elif payload == 'price':
        # Запуск калькулятора стоимости услуг
        await state.set_state(QuizOrder.city)
        await message.answer("🧮 Давайте рассчитаем стоимость наших услуг. Какой тип объекта?")
    else:
        # Стандартное главное меню
        await message.answer("Выберите действие:", reply_markup=get_main_menu())


@router.message(F.contact)
async def handle_contact(message: Message, state: FSMContext):
    """Обработка полученного контакта"""
    await state.update_data(phone=message.contact.phone_number)
    await state.set_state(QuizOrder.city)
    await message.answer("📋 Кто вы? (Собственник/Дизайнер/Застройщик/Инвестор/Другое)")


@router.message(F.text == "📋 Кто вы? (Собственник/Дизайнер/Застройщик/Инвестор/Другое)")
async def handle_quiz_start(message: Message, state: FSMContext):
    """Обработка начала квиза после получения контакта"""
    await state.set_state(QuizOrder.city)
    await message.answer("📋 Кто вы? (Собственник/Дизайнер/Застройщик/Инвестор/Другое)")