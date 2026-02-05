from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from .quiz import QuizOrder, handle_initial_contact
from keyboards.main_menu import get_consent_keyboard, get_main_menu
from database.db import db
from aiogram.types import ReplyKeyboardRemove
from datetime import datetime
import re
from utils.moderation import contains_bad_words

router = Router()

class UserProfile(StatesGroup):
    waiting_for_birthday = State()

@router.message(F.text.startswith("/start"))
async def handle_start(message: Message, state: FSMContext):
    parts = message.text.split()
    payload = parts[1] if len(parts) > 1 else ""
    await state.update_data(_payload=payload)

    user_id = message.from_user.id
    user = await db.get_or_create_user(
        user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name
    )

    # Проверяем наличие контакта
    if user.get('phone'):
        # Если контакт есть, проверяем статус квиза
        if await db.is_quiz_completed(user_id):
            if payload == "quiz":
                await message.answer("Вы уже заполнили заявку! Наш эксперт скоро свяжется с вами.")
            await message.answer("Главное меню ТЕРИОН:", reply_markup=get_main_menu())
        else:
            # Начинаем или продолжаем квиз (Шаг 1: Город)
            await state.set_state(QuizOrder.city)
            await message.answer(
                "📋 <b>Начинаем квалификацию</b>\n\n1. Укажите город / населенный пункт.",
                parse_mode="HTML",
                reply_markup=ReplyKeyboardRemove()
            )
        return

    # Если контакта нет — ВСЕГДА приветствие и согласие
    await message.answer(
        "Вас приветствует компания ТЕРИОН! Я — Антон, ИИ-помощник.\n\n"
        "Нажимая кнопку ниже, вы даете согласие на обработку персональных данных, "
        "получение уведомлений и информационную переписку. "
        "Все консультации носят информационный характер, финальное решение подтверждает эксперт ТЕРИОН.",
        reply_markup=get_consent_keyboard(),
        parse_mode="HTML"
    )


@router.message(F.contact)
async def handle_contact_start(message: Message, state: FSMContext):
    """Первичная обработка контакта"""
    # Сохраняем лид и уведомляем админа
    await handle_initial_contact(message, state)
    
    # Квиз запускается сразу после получения контакта
    await state.set_state(QuizOrder.city)
    await message.answer("📋 <b>Начинаем квиз</b>\n\n1. Укажите город / населенный пункт.", parse_mode="HTML", reply_markup=ReplyKeyboardRemove())


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
