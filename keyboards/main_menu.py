"""
Главное меню — кнопки для пользователей и админов.
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Bot
from config import ADMIN_ID
import os


def get_contact_keyboard():
    """Кнопка отправки контакта"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить контакт и согласиться", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_main_menu(user_id: int = None) -> ReplyKeyboardMarkup:
    """Главное меню для пользователей"""
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Записаться на консультацию")],
            [KeyboardButton(text="💬 Задать вопрос")],
        ],
        resize_keyboard=True
    )
    return markup


def get_admin_menu() -> ReplyKeyboardMarkup:
    """Меню админа"""
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛠 Создать пост")],
            [KeyboardButton(text="🕵️‍♂️ Темы от Шпиона")],
            [KeyboardButton(text="📅 Очередь постов")],
        ],
        resize_keyboard=True
    )
    return markup


def get_content_menu() -> InlineKeyboardMarkup:
    """Меню создания контента"""
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📸 С фото", callback_data="menu:photo"))
    markup.add(InlineKeyboardButton("📝 Только текст", callback_data="menu:editor"))
    markup.add(InlineKeyboardButton("🎨 Сгенерировать картинку", callback_data="menu:create"))
    markup.add(InlineKeyboardButton("◀️ Назад", callback_data="content_back"))
    return markup


def get_back_btn() -> InlineKeyboardMarkup:
    """Кнопка назад"""
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton("◀️ Назад", callback_data="content_back")
    )


def get_approve_post_btn(post_id: int) -> InlineKeyboardMarkup:
    """Кнопки аппрува поста"""
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{post_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{post_id}")
    )
    markup.add(InlineKeyboardButton("✏️ Редактировать", callback_data=f"edit_{post_id}"))
    return markup


def get_urgent_btn() -> InlineKeyboardMarkup:
    """Кнопки срочной публикации"""
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🚀 Опубликовать сейчас", callback_data="urgent_publish"),
        InlineKeyboardButton("📝 Доработать", callback_data="urgent_edit")
    )
    return markup


async def send_main_menu(bot: Bot, chat_id: int, user_id: int = None):
    """Отправка главного меню"""
    text = (
        "🏢 <b>Вас приветствует компания ТЕРИОН!</b>\n\n"
        "Я — Антон, ИИ-помощник по перепланировкам.\n\n"
        "📞 <b>Все консультации носят информационный характер.</b>\n"
        "Финальное решение подтверждает эксперт ТЕРИОН.\n\n"
        "Выберите действие:"
    )
    
    if str(user_id) == str(ADMIN_ID) or user_id == ADMIN_ID:
        markup = get_admin_menu()
        text = (
            "🎯 <b>Главное меню</b>\n\n"
            "🛠 <b>Создать пост</b> — Текст → Фото → Публикация\n"
            "🕵️‍♂️ <b>Темы от Шпиона</b> — ScoutAgent ищет идеи\n"
            "📅 <b>Очередь постов</b> — что запланировано на 12:00\n\n"
            "Выберите:"
        )
    else:
        markup = get_main_menu(user_id)
    
    await bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")


def is_admin(user_id: int) -> bool:
    """Проверка админа"""
    admin_id = os.getenv("ADMIN_ID", ADMIN_ID)
    return str(user_id) == str(admin_id)
