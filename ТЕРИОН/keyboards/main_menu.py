"""
Клавиатуры для главного меню и навигации
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from os import getenv


def get_main_menu() -> InlineKeyboardMarkup:
    """Главное меню бота"""
    # URL Mini App (настроить в .env или использовать локальный)
    mini_app_url = getenv("MINI_APP_URL", "https://your-domain.com/mini_app/")
    
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
                text="💰 Инвест-калькулятор",
                callback_data="mode:invest"
            )],
            [InlineKeyboardButton(
                text="🌐 Mini App: Инвест-калькулятор",
                web_app=WebAppInfo(url=mini_app_url)
            )]
        ]
    )


def get_consent_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура согласия на обработку данных"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Согласен и хочу продолжить")],
            [KeyboardButton(text="❌ Отказаться")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_contact_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура запроса контакта с request_contact=True"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить контакт и согласиться", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_name_confirmation_keyboard(name: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения имени"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"✅ Да, {name}",
                callback_data=f"confirm_name:{name}"
            )],
            [InlineKeyboardButton(
                text="✏️ Нет, указать другое",
                callback_data="change_name"
            )]
        ]
    )


def get_object_type_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа объекта"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Квартира", callback_data="obj:kvartira")],
            [InlineKeyboardButton(text="🏢 Коммерция", callback_data="obj:kommercia")],
            [InlineKeyboardButton(text="🏡 Дом", callback_data="obj:dom")]
        ]
    )


def get_remodeling_status_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура статуса перепланировки"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Выполнена", callback_data="remodel:done")],
            [InlineKeyboardButton(text="📋 Планируется", callback_data="remodel:planned")],
            [InlineKeyboardButton(text="🔄 В процессе", callback_data="remodel:in_progress")]
        ]
    )


def get_bti_documents_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура наличия документов БТИ"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Есть все документы", callback_data="bti:all")],
            [InlineKeyboardButton(text="📄 Есть частично", callback_data="bti:partial")],
            [InlineKeyboardButton(text="❌ Нет документов", callback_data="bti:none")]
        ]
    )


def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Вернуться в меню", callback_data="back_to_menu")]
        ]
    )


def get_continue_or_menu_keyboard() -> InlineKeyboardMarkup:
    """Продолжить диалог или вернуться в меню"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💬 Продолжить вопросы", callback_data="mode:dialog")],
            [InlineKeyboardButton(text="📝 Оставить заявку", callback_data="mode:quiz")],
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")]
        ]
    )
