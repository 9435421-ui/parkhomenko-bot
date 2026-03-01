"""
Admin Panel — управление ресурсами и ключевыми словами.
Команда: /admin
aiogram 2.x версия
"""
from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import logging
import os

from database import db
from config import (
    ADMIN_ID, JULIA_USER_ID, NOTIFICATIONS_CHANNEL_ID, THREAD_ID_LOGS,
    LEADS_GROUP_CHAT_ID, THREAD_ID_DRAFTS, BOT_TOKEN,
)
from services.scout_parser import scout_parser

logger = logging.getLogger(__name__)


class AdminStates(StatesGroup):
    wait_resource_link = State()
    wait_keyword = State()
    wait_lead_reply = State()
    wait_add_target_link = State()
    wait_draft_edit_text = State()


def check_admin(user_id: int) -> bool:
    """Проверка прав администратора"""
    if user_id == ADMIN_ID:
        return True
    if JULIA_USER_ID and JULIA_USER_ID != 0 and user_id == JULIA_USER_ID:
        return True
    logger.warning(f"⛔ Доступ запрещен: user_id={user_id}")
    return False


def get_admin_keyboard() -> types.InlineKeyboardMarkup:
    """Главное меню админ-панели"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton(text="➕ Добавить ресурс", callback_data="admin_add_resource"),
        types.InlineKeyboardButton(text="📋 Список ресурсов", callback_data="admin_list_resources"),
        types.InlineKeyboardButton(text="🔑 Ключевые слова", callback_data="admin_keywords"),
        types.InlineKeyboardButton(text="🕵️ Управление Шпионом", callback_data="admin_spy_panel"),
        types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back"),
    )
    return kb


def get_resource_type_keyboard() -> types.InlineKeyboardMarkup:
    """Выбор типа ресурса"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton(text="💬 Telegram чат", callback_data="admin_type:telegram"),
        types.InlineKeyboardButton(text="📘 VK группа", callback_data="admin_type:vk"),
        types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu"),
    )
    return kb


def get_keywords_keyboard() -> types.InlineKeyboardMarkup:
    """Меню ключевых слов"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton(text="➕ Добавить слово", callback_data="admin_add_keyword"),
        types.InlineKeyboardButton(text="📋 Список слов", callback_data="admin_list_keywords"),
        types.InlineKeyboardButton(text="◀️ Назад", callback_data="admin_menu"),
    )
    return kb


def get_back_to_admin() -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(text="◀️ Админ-панель", callback_data="admin_menu"))
    return kb


async def get_spy_panel_keyboard() -> types.InlineKeyboardMarkup:
    """Клавиатура пульта шпиона"""
    notify = await db.get_setting("spy_notify_enabled", "1")
    notify_label = "🔔 Уведомления: ВЫКЛ" if notify != "1" else "🔔 Уведомления: ВКЛ"
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton(text="📊 Статистика (24ч)", callback_data="spy_panel_stats"),
        types.InlineKeyboardButton(text="📝 Ключевые слова", callback_data="spy_panel_keywords"),
        types.InlineKeyboardButton(text="🌐 Ресурсы", callback_data="spy_panel_resources"),
        types.InlineKeyboardButton(text=notify_label, callback_data="spy_panel_toggle_notify"),
        types.InlineKeyboardButton(text="◀️ В админ-меню", callback_data="admin_menu"),
    )
    return kb


def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков админ-панели"""
    
    @dp.message_handler(commands=["admin"])
    async def cmd_admin(message: types.Message):
        """Главная команда админ-панели"""
        if not check_admin(message.from_user.id):
            await message.answer("⛔ У вас нет доступа к админ-панели.")
            return
        await message.answer(
            "🔧 <b>Админ-панель</b>\n\nВыберите действие:",
            reply_markup=get_admin_keyboard(),
            parse_mode="HTML"
        )
    
    @dp.callback_query_handler(lambda c: c.data == "admin_menu")
    async def admin_menu(callback: types.CallbackQuery):
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
    
    @dp.callback_query_handler(lambda c: c.data == "admin_add_resource")
    async def admin_add_resource(callback: types.CallbackQuery):
        """Начало добавления ресурса"""
        if not check_admin(callback.from_user.id):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        await callback.message.edit_text(
            "Выберите тип ресурса:",
            reply_markup=get_resource_type_keyboard()
        )
        await callback.answer()
    
    @dp.callback_query_handler(lambda c: c.data.startswith("admin_type:"))
    async def admin_select_type(callback: types.CallbackQuery, state: FSMContext):
        """Выбор типа ресурса"""
        if not check_admin(callback.from_user.id):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        resource_type = callback.data.split(":")[1]
        await state.update_data(resource_type=resource_type)
        await AdminStates.wait_resource_link.set()
        await callback.message.edit_text(
            f"Отправьте ссылку на {'Telegram чат' if resource_type == 'telegram' else 'VK группу'}:\n"
            f"(например: https://t.me/chatname или https://vk.com/groupname)"
        )
        await callback.answer()
    
    @dp.message_handler(state=AdminStates.wait_resource_link)
    async def admin_save_resource(message: types.Message, state: FSMContext):
        """Сохранение ресурса"""
        if not check_admin(message.from_user.id):
            await message.answer("⛔ У вас нет доступа.")
            return
        
        data = await state.get_data()
        resource_type = data.get("resource_type")
        link = message.text.strip()
        
        try:
            await db.add_target_resource(link=link, resource_type=resource_type)
            await message.answer(
                f"✅ Ресурс добавлен:\n<code>{link}</code>",
                reply_markup=get_back_to_admin(),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка добавления ресурса: {e}")
            await message.answer(
                f"❌ Ошибка добавления ресурса: {e}",
                reply_markup=get_back_to_admin()
            )
        await state.finish()
    
    @dp.callback_query_handler(lambda c: c.data == "admin_list_resources")
    async def admin_list_resources(callback: types.CallbackQuery):
        """Список ресурсов"""
        if not check_admin(callback.from_user.id):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        
        try:
            resources = await db.get_target_resources()
            if not resources:
                text = "📋 <b>Список ресурсов пуст</b>"
            else:
                text = "📋 <b>Список ресурсов:</b>\n\n"
                for r in resources:
                    status = "🟢" if r.get("is_active") else "🔴"
                    text += f"{status} <code>{r.get('link', 'N/A')}</code> ({r.get('resource_type', 'unknown')})\n"
            
            await callback.message.edit_text(text, reply_markup=get_back_to_admin(), parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка получения списка ресурсов: {e}")
            await callback.message.edit_text(
                f"❌ Ошибка: {e}",
                reply_markup=get_back_to_admin()
            )
        await callback.answer()
    
    @dp.callback_query_handler(lambda c: c.data == "admin_keywords")
    async def admin_keywords(callback: types.CallbackQuery):
        """Меню ключевых слов"""
        if not check_admin(callback.from_user.id):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        await callback.message.edit_text(
            "🔑 <b>Управление ключевыми словами</b>",
            reply_markup=get_keywords_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
    
    @dp.callback_query_handler(lambda c: c.data == "admin_add_keyword")
    async def admin_add_keyword(callback: types.CallbackQuery, state: FSMContext):
        """Начало добавления ключевого слова"""
        if not check_admin(callback.from_user.id):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        await AdminStates.wait_keyword.set()
        await callback.message.edit_text(
            "Введите ключевое слово или фразу:\n"
            "(например: перепланировка, согласование, БТИ)"
        )
        await callback.answer()
    
    @dp.message_handler(state=AdminStates.wait_keyword)
    async def admin_save_keyword(message: types.Message, state: FSMContext):
        """Сохранение ключевого слова"""
        if not check_admin(message.from_user.id):
            await message.answer("⛔ У вас нет доступа.")
            return
        
        keyword = message.text.strip()
        try:
            await db.add_spy_keyword(keyword)
            await message.answer(
                f"✅ Ключевое слово добавлено: <code>{keyword}</code>",
                reply_markup=get_back_to_admin(),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка добавления ключевого слова: {e}")
            await message.answer(
                f"❌ Ошибка: {e}",
                reply_markup=get_back_to_admin()
            )
        await state.finish()
    
    @dp.callback_query_handler(lambda c: c.data == "admin_list_keywords")
    async def admin_list_keywords(callback: types.CallbackQuery):
        """Список ключевых слов"""
        if not check_admin(callback.from_user.id):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        
        try:
            keywords = await db.get_spy_keywords()
            if not keywords:
                text = "🔑 <b>Список ключевых слов пуст</b>"
            else:
                text = "🔑 <b>Ключевые слова:</b>\n\n"
                for k in keywords:
                    status = "🟢" if k.get("is_active") else "🔴"
                    text += f"{status} <code>{k.get('keyword', 'N/A')}</code>\n"
            
            await callback.message.edit_text(text, reply_markup=get_back_to_admin(), parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка получения списка ключевых слов: {e}")
            await callback.message.edit_text(
                f"❌ Ошибка: {e}",
                reply_markup=get_back_to_admin()
            )
        await callback.answer()
    
    @dp.callback_query_handler(lambda c: c.data == "admin_spy_panel")
    async def spy_panel_open(callback: types.CallbackQuery):
        """Открытие панели шпиона"""
        if not check_admin(callback.from_user.id):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        kb = await get_spy_panel_keyboard()
        await callback.message.edit_text(
            "🕵️ <b>Пульт управления Шпионом</b>\n\n"
            "Выберите действие:",
            reply_markup=kb,
            parse_mode="HTML"
        )
        await callback.answer()
    
    @dp.callback_query_handler(lambda c: c.data == "spy_panel_toggle_notify")
    async def spy_panel_toggle_notify(callback: types.CallbackQuery):
        """Переключение уведомлений"""
        if not check_admin(callback.from_user.id):
            await callback.answer("⛔ Нет доступа", show_alert=True)
            return
        
        current = await db.get_setting("spy_notify_enabled", "1")
        new_val = "0" if current == "1" else "1"
        await db.set_setting("spy_notify_enabled", new_val)
        
        kb = await get_spy_panel_keyboard()
        status = "ВКЛ" if new_val == "1" else "ВЫКЛ"
        await callback.message.edit_text(
            f"🕵️ <b>Пульт управления Шпионом</b>\n\n"
            f"🔔 Уведомления: <b>{status}</b>",
            reply_markup=kb,
            parse_mode="HTML"
        )
        await callback.answer(f"Уведомления {status}")
    
    @dp.callback_query_handler(lambda c: c.data == "admin_back")
    async def admin_back(callback: types.CallbackQuery):
        """Возврат назад"""
        await callback.message.delete()
        await callback.answer()
