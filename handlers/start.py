from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from handlers.quiz import QuizOrder
from keyboards.main_menu import get_consent_keyboard, get_main_menu

router = Router()

@router.message(F.text.startswith("/start"))
async def handle_start(message: Message, state: FSMContext):
    payload = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    await message.answer(
        "Здравствуйте! Я — ваш цифровой помощник по вопросам перепланировок.\n\n"
        "Нажимая кнопку \"✅ Я согласен и хочу продолжить\", вы даете согласие на обработку персональных данных, "
        "принимаете условия политики конфиденциальности, а также соглашаетесь на получение информационных сообщений.\n\n"
        "Все консультации в автоматическом режиме носят ознакомительный характер, финальное решение всегда подтверждает наш эксперт.",
        reply_markup=get_consent_keyboard()
    )
    await state.update_data(_payload=payload)


@router.message(F.text == "✅ Я согласен и хочу продолжить")
async def handle_consent(message: Message, state: FSMContext):
    """Обработка согласия пользователя"""
    data = await state.get_data()
    payload = data.get('_payload', '')
    
    if payload == 'quiz' or payload == 'terion_main' or payload == 'domgrand':
        # Запуск квиза
        await state.set_state(QuizOrder.role)
        await message.answer("📋 Кто вы? (Собственник/Дизайнер/Застройщик/Инвестор/Другое)")
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


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    await callback.message.answer("Главное меню:", reply_markup=get_main_menu())
    await callback.answer()
