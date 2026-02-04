from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from handlers.quiz import QuizOrder
from keyboards.main_menu import get_consent_keyboard, get_main_menu

router = Router()

@router.message(F.text.startswith("/start"))
async def handle_start(message: Message, state: FSMContext):
    payload = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    await state.set_state(QuizOrder.city)
    await message.answer(
        "Вас приветствует компания ТЕРИОН! Я — Антон, ИИ-помощник. Нажимая кнопку ниже, вы даете согласие на обработку персональных данных, получение уведомлений и информационную переписку.\n\n"
        "Все мои консультации носят информационный характер, финальное решение всегда подтверждает эксперт, Юлия Пархоменко.",
        reply_markup=get_consent_keyboard(request_contact=True)
    )
    await state.update_data(_payload=payload)


@router.message(F.text == "✅ Согласен и хочу продолжить")
async def handle_consent(message: Message, state: FSMContext):
    """Обработка согласия пользователя"""
    data = await state.get_data()
    payload = data.get('_payload', '')

    # Получаем контакт
    contact = message.contact
    if contact:
        name = contact.first_name
        phone = contact.phone_number
        await state.update_data(name=name, phone=phone)
    else:
        # Если контакт не получен, пытаемся получить из профиля
        name = message.from_user.first_name
        await state.update_data(name=name)

    if payload == 'quiz':
        # Запуск квиза
        await state.set_state(QuizOrder.city)
        await message.answer(f"Приятно познакомиться, {name}! Давайте уточним детали по вашему объекту, чтобы я подготовил информацию для эксперта.")
        await message.answer("Какой город/населенный пункт?")
    elif payload == 'invest':
        # Запуск инвестиционного калькулятора
        await state.set_state(QuizOrder.city)
        await message.answer(f"Приятно познакомиться, {name}! Давайте оценим капитализацию вашего объекта после перепланировки. Какой город?")
    elif payload == 'expert':
        # Запуск экспертизы
        await state.set_state(QuizOrder.city)
        await message.answer(f"Приятно познакомиться, {name}! Какой тип недвижимости? (Жилая/Коммерческая/Инвестиционная)")
        await message.answer("❓ Есть ли ипотека/банк на объекте?")
    elif payload == 'price':
        # Запуск калькулятора стоимости услуг
        await state.set_state(QuizOrder.city)
        await message.answer(f"Приятно познакомиться, {name}! Давайте рассчитаем стоимость наших услуг. Какой тип объекта?")
    else:
        # Стандартное главное меню
        await message.answer(f"Приятно познакомиться, {name}! Выберите действие:", reply_markup=get_main_menu())
