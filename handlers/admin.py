"""
Admin Panel — управление ресурсами и ключевыми словами.
Команда: /admin
aiogram 3.x версия
"""
from aiogram import Router, F, Dispatcher
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging

from database import db
from config import ADMIN_ID, JULIA_USER_ID

logger = logging.getLogger(__name__)
router = Router()


class AdminStates(StatesGroup):
    wait_resource_link = State()
    wait_keyword = State()


def check_admin(user_id: int) -> bool:
    """Проверка прав администратора"""
    if user_id == ADMIN_ID:
        return True
    if JULIA_USER_ID and JULIA_USER_ID != 0 and user_id == JULIA_USER_ID:
        return True
    return False


def get_admin_keyboard():
    """Главное меню админ-панели"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ресурс", callback_data="admin_add_resource")],
        [InlineKeyboardButton(text="📋 Список ресурсов", callback_data="admin_list_resources")],
        [InlineKeyboardButton(text="🔑 Ключевые слова", callback_data="admin_keywords")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")],
    ])
    return kb


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Главная команда админ-панели"""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return
    await message.answer(
        "🔧 <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin_menu")
async def admin_menu(callback: CallbackQuery):
    """Возврат в главное меню"""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    await callback.message.edit_text(
        "🔧 <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков админ-панели"""
    dp.include_router(router)
