from aiogram import Router, F
from aiogram.types import Message, ContentType
from aiogram.fsm.context import FSMContext
from handlers.quiz import QuizOrder
from keyboards.main_menu import get_consent_keyboard, get_main_menu
from config import LEADS_GROUP_CHAT_ID

router = Router()

# Текст приветствия
GREETING_TEXT = (
    "Вас приветствует компания ТЕРИОН!\n"
    "Я — Антон, ваш ИИ-помощник. Нажимая кнопку ниже, вы даете согласие на обработку "
    "персональных данных, получение уведомлений и информационную переписку.\n\n"
    "Все консультации носят информационный характер, финальное решение подтверждает эксперт ТЕРИОН."
)

# Финальный текст пользователю
FINAL_TEXT = (
    "{user_name}, спасибо! Я отправил эксперту компании ТЕРИОН полученную от вас информацию.\n"
    "Мы свяжемся с вами в рабочее время с 9:00 до 20:00 по МСК.\n\n"
    "Если у вас остались вопросы или вы хотите отправить дополнительные документы, "
    "вы можете оставить информацию в чате — я всё передам специалисту."
)


@router.message(F.text.startswith("/start"))
async def handle_start(message: Message, state: FSMContext):
    payload = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""
    
    await message.answer(
        GREETING_TEXT,
        reply_markup=get_consent_keyboard()
    )
    await state.update_data(_payload=payload)


@router.message(F.text == "✅ Согласен и хочу продолжить")
async def handle_consent(message: Message, state: FSMContext):
    """Обработка согласия пользователя - сразу запрашиваем контакт"""
    data = await state.get_data()
    payload = data.get('_payload', '')

    if payload == 'quiz':
        # Запрос контакта перед началом квиза с кнопкой request_contact=True
        await message.answer(
            "Для начала квиза мне нужен ваш контакт. Пожалуйста, поделитесь вашим номером телефона.",
            reply_markup=message.bot.get_contact_request_button("📱 Отправить контакт и согласиться")
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
    """Обработка полученного контакта - сохраняем и запускаем квиз"""
    await state.update_data(
        phone=message.contact.phone_number,
        user_name=message.from_user.full_name or message.from_user.first_name or "Клиент"
    )
    await state.set_state(QuizOrder.city)
    
    # Сразу переходим к вопросам квиза
    await message.answer("🏙 В каком городе находится ваш объект?")


@router.message(F.text == "📋 Кто вы? (Собственник/Дизайнер/Застройщик/Инвестор/Другое)")
async def handle_quiz_start(message: Message, state: FSMContext):
    """Обработка начала квиза после получения контакта"""
    await state.set_state(QuizOrder.city)
    await message.answer("🏙 В каком городе находится ваш объект?")
