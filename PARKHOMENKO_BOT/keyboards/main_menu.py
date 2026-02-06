"""
Клавиатуры для главного меню и навигации
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from os import getenv


def get_main_menu() -> InlineKeyboardMarkup:
    """Главное меню бота"""
    mini_app_url = getenv("MINI_APP_URL", "https://ternion.ru/mini_app/")

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Оставить заявку (Quiz V2.0)", callback_data="mode:quiz")],
            [InlineKeyboardButton(text="💬 Задать вопрос консультанту", callback_data="mode:dialog")],
            [InlineKeyboardButton(text="💰 Инвест-калькулятор", callback_data="mode:invest")],
            [InlineKeyboardButton(text="🚀 Открыть Mini App", web_app=WebAppInfo(url=mini_app_url))]
        ]
    )


def get_consent_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Согласен и хочу продолжить")], [KeyboardButton(text="❌ Отказаться")]],
        resize_keyboard=True, one_time_keyboard=True
    )


def get_contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )


def get_object_type_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Квартира")],
            [KeyboardButton(text="Коммерция")]
        ],
        resize_keyboard=True, one_time_keyboard=True
    )


def get_remodeling_status_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Выполнена")],
            [KeyboardButton(text="Планируется")]
        ],
        resize_keyboard=True, one_time_keyboard=True
    )

def get_name_confirmation_keyboard(name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"✅ Да, {name}", callback_data=f"confirm_name:{name}")]])

def get_bti_documents_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📄 Документы", callback_data="bti")]])

def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Меню", callback_data="back_to_menu")]])

def get_continue_or_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💬 Продолжить", callback_data="mode:dialog")]])
