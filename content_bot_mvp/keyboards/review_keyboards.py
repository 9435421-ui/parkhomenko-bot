from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_review_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Утвердить", callback_data=f"approve:{post_id}"),
            InlineKeyboardButton(text="✏️ Править", callback_data=f"edit:{post_id}")
        ],
        [
            InlineKeyboardButton(text="⏰ Запланировать", callback_data=f"schedule:{post_id}")
        ]
    ])
