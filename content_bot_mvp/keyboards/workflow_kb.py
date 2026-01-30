from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def get_workflow_keyboard(item_id: int, current_status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if current_status == 'idea':
        builder.row(InlineKeyboardButton(text="📝 Создать черновик", callback_data=f"wf_draft_{item_id}"))

    elif current_status == 'draft':
        builder.row(InlineKeyboardButton(text="✏️ Править", callback_data=f"wf_edit_{item_id}"))
        builder.row(InlineKeyboardButton(text="🧐 На проверку", callback_data=f"wf_review_{item_id}"))

    elif current_status == 'review':
        builder.row(InlineKeyboardButton(text="✅ Утвердить", callback_data=f"wf_approve_{item_id}"))
        builder.row(InlineKeyboardButton(text="❌ На доработку", callback_data=f"wf_draft_{item_id}"))

    elif current_status == 'approved':
        builder.row(InlineKeyboardButton(text="🕒 В расписание", callback_data=f"wf_schedule_{item_id}"))
        builder.row(InlineKeyboardButton(text="🚀 Опубликовать сейчас", callback_data=f"wf_publish_{item_id}"))

    elif current_status == 'scheduled':
        builder.row(InlineKeyboardButton(text="🚀 Опубликовать сейчас", callback_data=f"wf_publish_{item_id}"))
        builder.row(InlineKeyboardButton(text="🛑 Отменить план", callback_data=f"wf_approve_{item_id}"))

    return builder.as_markup()
