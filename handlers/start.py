"""
Обработчики команды /start и онбординга
"""
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from database import db
from keyboards import get_main_menu, get_consent_keyboard, get_contact_keyboard, get_name_confirmation_keyboard

router = Router()

# Тексты для онбординга
GREETING_TEXT = (
    "👋 Здравствуйте! Я Антон, <b>ИИ-помощник эксперта Пархоменко Юлии Владимировны</b> "
    "по согласованию перепланировок.\n\n"
    "Я помогу вам:\n"
    "• Разобраться в нормах и требованиях\n"
    "• Оценить возможность вашей перепланировки\n"
    "• Оформить заявку на консультацию\n\n"
    "Для продолжения необходимо ваше согласие:"
)


@router.message(CommandStart())
async def cmd_start(message: Message):
    """
    Обработка команды /start с поддержкой Deep Links
    
    Deep Links:
    - /start quiz - запуск квиза
    - /start invest - инвест-калькулятор
    - /start ask - прямой вопрос консультанту
    """
    user_id = message.from_user.id
    
    # Получаем или создаём пользователя в БД
    await db.get_or_create_user(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )
    
    # Извлекаем deep link параметр
    deep_link = None
    if message.text and ' ' in message.text:
        deep_link = message.text.split(' ', 1)[1]
    
    # Проверяем состояние пользователя
    state = await db.get_user_state(user_id)
    
    # Если пользователь впервые - показываем согласие
    if not state or not state.get('consent_given'):
        # Сохраняем deep link для использования после онбординга
        if deep_link:
            await db.update_user_state(user_id, pending_deep_link=deep_link)
        await show_privacy_consent(message)
        return
    
    # Если согласие есть, но нет контакта - запрашиваем
    if not state.get('contact_received'):
        if deep_link:
            await db.update_user_state(user_id, pending_deep_link=deep_link)
        await request_contact(message)
        return
    
    # Обработка Deep Links
    if deep_link:
        await handle_deep_link(message, deep_link)
        return
    
    # Если есть отложенный deep link после онбординга
    if state.get('pending_deep_link'):
        pending_link = state['pending_deep_link']
        await db.update_user_state(user_id, pending_deep_link=None)
        await handle_deep_link(message, pending_link)
        return
    
    # Если всё есть и нет deep links - показываем главное меню
    await show_main_menu(message)


async def handle_deep_link(message: Message, deep_link: str):
    """Обработка Deep Links"""
    user_id = message.from_user.id
    
    if deep_link == "quiz":
        # Запуск квиза
        await db.update_user_state(user_id, mode="quiz", quiz_step=2)
        await message.answer(
            "📝 <b>Запуск квиза для оформления заявки</b>\n\n"
            "Я задам вам несколько вопросов, чтобы наш специалист мог подготовить "
            "предварительную консультацию.",
            parse_mode="HTML"
        )
        await message.answer(
            "Если у вас есть дополнительный способ связи (WhatsApp/почта/другой номер) — "
            "напишите его, или отправьте «нет»."
        )
    
    elif deep_link == "invest":
        # Инвест-калькулятор
        await db.update_user_state(user_id, mode="invest")
        await message.answer(
            "💰 <b>Инвест-калькулятор</b>\n\n"
            "Оценим потенциал вашей квартиры под перепланировку и капитализацию.\n\n"
            "📍 В каком городе находится квартира?",
            parse_mode="HTML"
        )
    
    elif deep_link == "ask":
        # Прямой вопрос консультанту
        await db.update_user_state(user_id, mode="dialog")
        state = await db.get_user_state(user_id)
        name = state.get('name', 'дорогой клиент')
        await message.answer(
            f"💬 <b>Консультация с Антоном</b>\n\n"
            f"{name}, я готов ответить на ваши вопросы по перепланировкам. "
            f"Опишите вашу ситуацию или задайте конкретный вопрос.",
            parse_mode="HTML"
        )
    
    else:
        # Неизвестный deep link - показываем меню
        await show_main_menu(message)


async def show_privacy_consent(message: Message):
    """Показать запрос согласия на обработку данных"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Согласен с политикой обработки ПД",
                callback_data="consent:privacy"
            )],
            [InlineKeyboardButton(
                text="✅ Согласен с офертой",
                callback_data="consent:offer"
            )]
        ]
    )
    
    await message.answer(GREETING_TEXT, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("consent:"))
async def consent_button_handler(callback: CallbackQuery):
    """Обработка нажатий на кнопки согласия"""
    user_id = callback.from_user.id
    consent_type = callback.data.split(":")[1]
    
    state = await db.get_user_state(user_id) or {}
    
    # Сохраняем согласия
    if consent_type == "privacy":
        await db.update_user_state(user_id, privacy_consent=True)
        state['privacy_consent'] = True
    elif consent_type == "offer":
        await db.update_user_state(user_id, offer_consent=True)
        state['offer_consent'] = True
    
    # Проверяем, оба ли согласия даны
    if state.get('privacy_consent') and state.get('offer_consent'):
        await db.update_user_state(user_id, consent_given=True)
        
        await callback.message.edit_text(
            "✅ Спасибо за согласие!\n\n"
            "Для идентификации вас в системе и возможности получения отчета, "
            "пожалуйста, подтвердите ваш контакт.",
            parse_mode="HTML"
        )
        
        # Запрашиваем контакт
        await request_contact(callback.message)
        await callback.answer()
    else:
        # Ещё не все согласия даны
        missing = []
        if not state.get('privacy_consent'):
            missing.append("политику обработки ПД")
        if not state.get('offer_consent'):
            missing.append("оферту")
        
        await callback.answer(
            f"Пожалуйста, согласитесь также с: {', '.join(missing)}",
            show_alert=True
        )


async def request_contact(message: Message):
    """Запрос контакта пользователя"""
    markup = get_contact_keyboard()
    await message.answer(
        "Для продолжения работы поделитесь своим контактом Telegram — "
        "это защитит нас от спама и поможет быстрее связаться.",
        reply_markup=markup
    )


@router.message(F.contact)
async def contact_received(message: Message):
    """Обработка полученного контакта"""
    user_id = message.from_user.id
    phone = message.contact.phone_number
    
    # Сохраняем телефон
    await db.update_user_state(
        user_id,
        phone=phone,
        contact_received=True
    )
    
    # Получаем имя из контакта
    contact_name = message.contact.first_name or ""
    
    if contact_name:
        # Если имя есть - предлагаем подтвердить
        markup = get_name_confirmation_keyboard(contact_name)
        await message.answer(
            f"Спасибо! Ваш контакт {phone} сохранён.\n\n"
            f"Могу к вам обращаться «{contact_name}»?",
            reply_markup=markup
        )
    else:
        # Если имени нет - спрашиваем
        await message.answer(
            f"Спасибо! Ваш контакт {phone} сохранён.\n\n"
            "Как к вам обращаться?",
            reply_markup=ReplyKeyboardRemove()
        )
        await db.update_user_state(user_id, mode="waiting_name")


@router.callback_query(F.data.startswith("confirm_name:"))
async def confirm_name(callback: CallbackQuery):
    """Подтверждение имени"""
    user_id = callback.from_user.id
    name = callback.data.split(":", 1)[1]
    
    # Сохраняем имя
    await db.update_user_state(user_id, name=name)
    
    await callback.message.edit_text(f"Приятно познакомиться, {name}!")
    await show_main_menu(callback.message)
    await callback.answer()


@router.callback_query(F.data == "change_name")
async def change_name(callback: CallbackQuery):
    """Запрос нового имени"""
    user_id = callback.from_user.id
    
    await callback.message.edit_text("Хорошо, напишите, как к вам обращаться:")
    await db.update_user_state(user_id, mode="waiting_name")
    await callback.answer()


@router.message(F.text)
async def name_input(message: Message):
    """Обработка ввода имени"""
    user_id = message.from_user.id
    state = await db.get_user_state(user_id)
    
    if state and state.get('mode') == 'waiting_name':
        name = message.text.strip()
        
        await db.update_user_state(user_id, name=name, mode=None)
        await message.answer(f"Приятно познакомиться, {name}!")
        await show_main_menu(message)


@router.callback_query(F.data == "back_to_menu")
async def back_to_main_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    user_id = callback.from_user.id
    
    # Сбрасываем режим
    await db.update_user_state(user_id, mode=None, quiz_step=0)
    
    markup = get_main_menu()
    await callback.message.edit_text(
        "Чем Антон может вам помочь?",
        reply_markup=markup
    )
    await callback.answer()


async def show_main_menu(message: Message):
    """Показать главное меню"""
    markup = get_main_menu()
    await message.answer(
        "Чем Антон может вам помочь?",
        reply_markup=markup
    )
