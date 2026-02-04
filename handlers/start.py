from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from .quiz import QuizOrder, handle_initial_contact, start_quiz
from keyboards.main_menu import get_consent_keyboard, get_main_menu, get_contact_keyboard
from database.db import db
from datetime import datetime
import re

router = Router()

class UserProfile(StatesGroup):
    waiting_for_birthday = State()

@router.message(F.text.startswith("/start"))
async def handle_start(message: Message, state: FSMContext):
    parts = message.text.split()
    payload = parts[1] if len(parts) > 1 else ""

    if payload == 'quiz':
        await start_quiz(message, state)
        return

    await message.answer(
        "Здравствуйте! Я — Антон, ваш личный <b>ИИ-помощник</b> по вопросам перепланировок. Работаю от имени ведущего эксперта компании ТЕРИОН.\n\n"
        "Нажимая кнопку \"✅ Я согласен и хочу продолжить\", вы даете согласие на обработку персональных данных, "
        "принимаете условия политики конфиденциальности, а также соглашаетесь на получение информационных сообщений.\n\n"
        "Все консультации в автоматическом режиме носят ознакомительный характер, финальное решение всегда подтверждает наш эксперт.",
        reply_markup=get_consent_keyboard(),
        parse_mode="HTML"
    )
    await state.update_data(_payload=payload)


@router.message(F.text == "✅ Я согласен и хочу продолжить")
async def handle_consent(message: Message, state: FSMContext):
    """Обработка согласия пользователя"""
    await state.update_data(consent=True, consent_date=datetime.now().isoformat())

    await message.answer(
        "Спасибо! Теперь, пожалуйста, поделитесь вашим контактом, чтобы мы могли сохранить вашу заявку и связаться с вами.",
        reply_markup=get_contact_keyboard()
    )


@router.message(F.contact)
async def handle_contact_start(message: Message, state: FSMContext):
    """Первичная обработка контакта после согласия"""
    data = await state.get_data()
    if not data.get('consent'):
        await message.answer("Пожалуйста, сначала подтвердите согласие на обработку данных.", reply_markup=get_consent_keyboard())
        return

    # Сохраняем лид и уведомляем админа
    await handle_initial_contact(message, state)

    payload = data.get('_payload', '')
    
    if payload == 'quiz' or payload == 'terion_main' or payload == 'domgrand':
        await state.set_state(QuizOrder.role)
        await message.answer("📋 Кто вы? (Собственник/Дизайнер/Застройщик/Инвестор/Другое)")
    elif payload == 'invest':
        await state.set_state(QuizOrder.city)
        await message.answer("💰 Давайте оценим капитализацию вашего объекта после перепланировки. Какой город?")
    elif payload == 'expert':
        await state.set_state(QuizOrder.obj_type)
        await message.answer("🔍 Какой тип недвижимости? (🏠 Жилая/🏢 Коммерческая/💰 Инвестиционная)")
    elif payload == 'price':
        await state.set_state(QuizOrder.city)
        await message.answer("🧮 Давайте рассчитаем стоимость наших услуг. Какой тип объекта?")
    else:
        await message.answer("Выберите действие:", reply_markup=get_main_menu())


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    await callback.message.answer("Главное меню:", reply_markup=get_main_menu())
    await callback.answer()


@router.callback_query(F.data == "set_birthday")
async def ask_birthday(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "🎂 Укажите вашу дату рождения в формате <b>ДД.ММ</b> (например: 15.05),\n"
        "чтобы мы могли поздравить вас и подарить специальный бонус от ТЕРИОН!",
        parse_mode="HTML"
    )
    await state.set_state(UserProfile.waiting_for_birthday)
    await callback.answer()


@router.message(UserProfile.waiting_for_birthday)
async def save_birthday(message: Message, state: FSMContext):
    text = message.text.strip()
    if re.match(r'^\d{2}\.\d{2}$', text):
        await db.update_user_birthday(message.from_user.id, text)
        await message.answer(
            f"✅ Дата рождения {text} сохранена!\n\n"
            "В этот день мы обязательно пришлем вам подарок. 🎁",
            reply_markup=get_main_menu()
        )
        await state.clear()
    else:
        await message.answer("⚠️ Неверный формат. Пожалуйста, укажите дату как <b>ДД.ММ</b> (например, 01.12).")
