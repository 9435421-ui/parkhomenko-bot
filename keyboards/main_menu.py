"""
Клавиатуры - минимум кнопок
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def get_contact_keyboard():
    """Кнопка отправки контакта + согласие (request_contact=True)"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить контакт и согласиться", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_main_menu():
    """Главное меню - inline кнопки"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Записаться на консультацию", callback_data="mode:quiz")],
            [InlineKeyboardButton(text="💬 Задать вопрос консультанту", callback_data="mode:dialog")],
        ]
    )
