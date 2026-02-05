from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from handlers.quiz import QuizOrder
from keyboards.main_menu import get_consent_keyboard, get_main_menu

router = Router()

@router.message(F.text.startswith("/start"))
async def handle_start(message: Message, state: FSMContext):
    payload = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    await state.clear()  # Clear state on start
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
        # Запуск квиза
        await state.set_state(QuizOrder.city)
        await message.answer("🏙 В каком городе находится ваш объект?")
    elif payload == 'invest':
        # Запуск инвестиционного калькулятора
        await state.set_state(QuizOrder.city)
        await message.answer("💰 Давайте оценим капитализацию вашего объекта после перепланировки. Какой город?")
    elif payload == 'expert':
        # Запуск экспертизы (теперь через квиз)
        await state.set_state(QuizOrder.city)
        await message.answer("🔍 Для проведения экспертизы укажите, пожалуйста, город:")
    elif payload == 'price':
        # Запуск калькулятора стоимости (теперь через квиз)
        await state.set_state(QuizOrder.city)
        await message.answer("🧮 Для расчета стоимости укажите, пожалуйста, город:")
    else:
        # Стандартное главное меню
        await message.answer("Выберите действие:", reply_markup=get_main_menu())
