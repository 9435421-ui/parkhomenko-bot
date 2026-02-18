"""
Главное меню — кнопки для пользователей и админов.
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot
from config import ADMIN_ID, is_admin
import os


def get_contact_keyboard():
    """Кнопка отправки контакта"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить контакт и согласиться", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_main_menu(user_id: int | None = None) -> ReplyKeyboardMarkup:
    """Очищенное меню для ТЕРИОН — только самое важное"""
    # Оставляем пустую или минимальную клавиатуру, 
    # так как вход в квиз и консультации будет через прямые ссылки
    return ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True)


def get_admin_menu() -> ReplyKeyboardMarkup:
    """Меню админа — консультации, продажи, логика"""
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🕵️‍♂️ Темы от Шпиона")],
            [KeyboardButton(text="💰 Инвест-калькулятор")],
            [KeyboardButton(text="📝 Записаться на консультацию")],
        ],
        resize_keyboard=True
    )
    return markup


def get_content_menu() -> InlineKeyboardMarkup:
    """Меню создания контента (Текст, Фото, ИИ-Визуал). Публикация: TERION / ДОМ ГРАНД / MAX — в превью поста."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Текст", callback_data="content_text")],
        [InlineKeyboardButton(text="🖼 Фото", callback_data="content_photo")],
        [InlineKeyboardButton(text="🎨 ИИ-Визуал", callback_data="content_visual")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_menu")]
    ])


def get_back_btn() -> InlineKeyboardMarkup:
    """Кнопка назад"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("◀️ Назад", callback_data="content_back")]
    ])


def get_approve_post_btn(post_id: int) -> InlineKeyboardMarkup:
    """Кнопки аппрува поста. Публикация (TERION / ДОМ ГРАНД / MAX / VK) — под черновиком в рабочей группе или в контент-боте."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{post_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{post_id}")
        ],
        [InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{post_id}")]
    ])


def get_urgent_btn() -> InlineKeyboardMarkup:
    """Кнопки срочной публикации"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("🚀 Опубликовать сейчас", callback_data="urgent_publish"),
            InlineKeyboardButton("📝 Доработать", callback_data="urgent_edit")
        ]
    ])


async def send_main_menu(bot: Bot, chat_id: int, user_id: int | None = None):
    """Отправка главного меню"""
    text = (
        "🏢 <b>Вас приветствует компания ТЕРИОН!</b>\n\n"
        "Я — Антон, ИИ-помощник по перепланировкам.\n\n"
        "📞 <b>Все консультации носят информационный характер.</b>\n"
        "Финальное решение подтверждает эксперт ТЕРИОН.\n\n"
        "Выберите действие:"
    )
    
    if user_id and is_admin(user_id):
        markup = get_admin_menu()
        text = (
            "🎯 <b>Главное меню</b>\n\n"
            "🕵️‍♂️ <b>Темы от Шпиона</b> — идеи из чатов, сохранить в контент-план\n"
            "💰 <b>Инвест-калькулятор</b> — оценка прироста стоимости после перепланировки\n"
            "📝 <b>Записаться на консультацию</b> — запустить квиз\n\n"
            "<i>Публикации — в контент-боте</i>"
        )
    else:
        markup = get_main_menu(user_id)
    
    await bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")


def _is_admin_user(user_id: int) -> bool:
    """Проверка админа (дублирует config.is_admin для совместимости)."""
    return is_admin(user_id)
