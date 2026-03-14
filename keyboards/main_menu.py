"""
Главное меню — кнопки для пользователей и админов.
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot
from config import ADMIN_ID, is_admin
import os


def get_main_menu() -> InlineKeyboardMarkup:
    """Главное меню бота (только для админа)"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="📝 Оставить заявку (Quiz)",
                callback_data="mode:quiz"
            )],
            [InlineKeyboardButton(
                text="💬 Задать вопрос консультанту",
                callback_data="mode:dialog"
            )],
            [InlineKeyboardButton(
                text="🧮 Калькулятор перепланировки",
                callback_data="mode:invest"
            )]
        ]
    )


def _is_admin_user(user_id: int) -> bool:
    """Проверка админа (дублирует config.is_admin для совместимости)."""
    return is_admin(user_id)
