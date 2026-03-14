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


def get_contact_keyboard():
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Отправить контакт", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_admin_menu():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="📋 Лиды", callback_data="admin_leads")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")],
    ])


def get_urgent_btn():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Срочная консультация", callback_data="urgent_consult")],
    ])


def get_consent_keyboard():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Согласен", callback_data="consent_yes")],
        [InlineKeyboardButton(text="❌ Не согласен", callback_data="consent_no")],
    ])
