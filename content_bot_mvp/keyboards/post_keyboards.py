from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict

def get_channels_keyboard(channels: List[Dict]) -> InlineKeyboardMarkup:
    keyboard = []
    for channel in channels:
        keyboard.append([InlineKeyboardButton(
            text=f"{channel['channel_alias']} ({channel['brand']})",
            callback_data=f"channel:{channel['channel_alias']}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_themes_keyboard() -> InlineKeyboardMarkup:
    themes = [
        "Нормативная база",
        "Кейсы/Примеры",
        "Советы эксперта",
        "Новости рынка",
        "Инвестиции",
        "Свой вариант"
    ]
    keyboard = []
    for theme in themes:
        keyboard.append([InlineKeyboardButton(text=theme, callback_data=f"theme:{theme}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_skip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏩ Пропустить", callback_data="skip")]
    ])
