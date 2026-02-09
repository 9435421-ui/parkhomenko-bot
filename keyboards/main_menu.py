"""
Клавиатуры - минимум кнопок
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def get_contact_keyboard() -> ReplyKeyboardMarkup:
    """Кнопка отправки контакта (request_contact=True)"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить контакт и согласиться", request_contact=True)]],
        resize_keyboard=True
    )


def get_consent_keyboard() -> ReplyKeyboardMarkup:
    """Согласие на ПД"""
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
