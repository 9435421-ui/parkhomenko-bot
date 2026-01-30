from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from handlers.quiz import QuizOrder
from keyboards.main_menu import get_consent_keyboard, get_main_menu
from utils.time_utils import is_working_hours

router = Router()

@router.message(F.text.startswith("/start"))
async def handle_start(message: Message, state: FSMContext):
    payload = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""

    if is_working_hours():
        greeting = "Прежде чем мы начнем, я должен сообщить: я — цифровой помощник нашего эксперта по перепланировкам. "
    else:
        greeting = "Здравствуйте. Сейчас нерабочее время. Вы можете пройти опрос сейчас — наш специалист изучит заявку в рабочее время.\n\n"

    await message.answer(
        f"{greeting}"
        "Нажимая кнопку \"Начать\", вы даете согласие на обработку персональных данных и принимаете условия политики конфиденциальности, "
        "а также на отправку вам информационных сообщений и переписку.\n\n"
        "Все мои консультации носят информационный характер, финальное решение всегда подтверждает эксперт.",
        reply_markup=get_consent_keyboard()
    )
    await state.update_data(_payload=payload)


@router.message(F.text == "✅ Согласен и хочу продолжить")
async def handle_consent(message: Message, state: FSMContext):
    """Обработка согласия пользователя"""
    data = await state.get_data()
    payload = data.get('_payload', '')
    
    # Сначала запрашиваем телефон для мгновенного сохранения лида
    await state.set_state(QuizOrder.phone)
    await message.answer(
        "Спасибо за доверие! Пожалуйста, напишите ваш номер телефона для связи. "
        "Это поможет нашему эксперту быстрее подготовить информацию для вас."
    )
