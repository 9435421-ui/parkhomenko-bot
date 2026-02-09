"""
Клавиатуры - минимум кнопок
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def get_consent_keyboard() -> ReplyKeyboardMarkup:
    """Только согласие + контакт"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Согласен и хочу продолжить")],
        ],
        resize_keyboard=True
    )


def get_main_menu() -> InlineKeyboardMarkup:
    """Главное меню - только inline кнопки"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Записаться на консультацию", callback_data="mode:quiz")],
            [InlineKeyboardButton(text="💬 Задать вопрос консультанту", callback_data="mode:dialog")],
        ]
    )
