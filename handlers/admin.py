"""
Admin Panel — управление ресурсами и ключевыми словами.
Команда: /admin
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

from database import db
from config import ADMIN_ID, JULIA_USER_ID, NOTIFICATIONS_CHANNEL_ID, THREAD_ID_LOGS
from services.scout_parser import scout_parser

logger = logging.getLogger(__name__)
router = Router()


class AdminStates(StatesGroup):
    wait_resource_link = State()
    wait_keyword = State()


def check_admin(user_id: int) -> bool:
    """Проверка прав администратора"""
    return user_id == ADMIN_ID or (JULIA_USER_ID and user_id == JULIA_USER_ID)


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Главное меню админ-панели"""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить ресурс", callback_data="admin_add_resource")
    builder.button(text="📋 Список ресурсов", callback_data="admin_list_resources")
    builder.button(text="🔑 Ключевые слова", callback_data="admin_keywords")
    builder.button(text="◀️ Назад", callback_data="admin_back")
    builder.adjust(1, 1, 1, 1)
    return builder.as_markup()


def get_resource_type_keyboard() -> InlineKeyboardMarkup:
    """Выбор типа ресурса"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💬 Telegram чат", callback_data="admin_type:telegram")
    builder.button(text="📘 VK группа", callback_data="admin_type:vk")
    builder.button(text="◀️ Назад", callback_data="admin_menu")
    builder.adjust(1, 1, 1)
    return builder.as_markup()


def get_keywords_keyboard() -> InlineKeyboardMarkup:
    """Меню ключевых слов"""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить слово", callback_data="admin_add_keyword")
    builder.button(text="📋 Список слов", callback_data="admin_list_keywords")
    builder.button(text="◀️ Назад", callback_data="admin_menu")
    builder.adjust(1, 1, 1)
    return builder.as_markup()


def get_back_to_admin() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Админ-панель", callback_data="admin_menu")
    return builder.as_markup()


# === КОМАНДА /SPY_REPORT ===
@router.message(Command("spy_report"))
async def cmd_spy_report(message: Message):
    """Где был шпион: последний скан каналов и групп (только для админа)."""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа")
        return
    report = scout_parser.get_last_scan_report()
    await message.answer(report)


# === КОМАНДА /STATS (для рабочей группы) ===
@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Краткий отчёт шпиона: где сканировали, сколько постов (только для админа)."""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа")
        return
    report = scout_parser.get_last_scan_report()
    await message.answer(report)


# === КОМАНДА /HUNT (для рабочей группы) ===
@router.message(Command("hunt"))
async def cmd_hunt(message: Message):
    """Запуск охоты за лидами: скан TG/VK, анализ, отчёт в группу (только для админа)."""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа")
        return
    await message.answer("🏹 Запускаю охоту за лидами...")
    try:
        from services.lead_hunter import LeadHunter
        hunter = LeadHunter()
        await hunter.hunt()
        await message.answer("✅ Охота завершена. Отчёт — в топике «Логи».")
    except Exception as e:
        logger.exception("hunt")
        await message.answer(f"❌ Ошибка охоты: {e}")


# === КОМАНДА /ADMIN ===
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    """Главное меню админ-панели"""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к админ-панели")
        return
    
    await state.clear()
    await message.answer(
        "🔧 <b>Админ-панель TERION</b>\n\n"
        "Выберите действие:",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )


# === ОБРАБОТЧИКИ КНОПОК ===
@router.callback_query(F.data == "admin_menu")
async def admin_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    
    await state.clear()
    await callback.message.edit_text(
        "🔧 <b>Админ-панель TERION</b>\n\n"
        "Выберите действие:",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_resource")
async def admin_add_resource(callback: CallbackQuery):
    """Добавление ресурса - выбор типа"""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    
    await callback.message.edit_text(
        "➕ <b>Добавить ресурс</b>\n\n"
        "Выберите тип ресурса:",
        reply_markup=get_resource_type_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_type:"))
async def admin_select_type(callback: CallbackQuery, state: FSMContext):
    """Выбор типа ресурса - запрашиваем ссылку"""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    
    resource_type = callback.data.split(":")[1]
    await state.update_data(resource_type=resource_type)
    
    type_name = "Telegram чат" if resource_type == "telegram" else "VK группа"
    
    await callback.message.edit_text(
        f"➕ <b>Добавить {type_name}</b>\n\n"
        f"Отправьте ссылку на {type_name.lower()}:\n\n"
        f"Примеры:\n"
        f"• TG: t.me/c/1849161015/1\n"
        f"• VK: vk.com/himki",
        reply_markup=get_back_to_admin(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.wait_resource_link)
    await callback.answer()


@router.message(AdminStates.wait_resource_link)
async def admin_save_resource(message: Message, state: FSMContext):
    """Сохранение ресурса"""
    data = await state.get_data()
    resource_type = data.get("resource_type")
    link = message.text.strip()
    
    # Простая валидация
    if resource_type == "telegram" and "t.me" not in link:
        await message.answer("❌ Неверная ссылка Telegram", reply_markup=get_back_to_admin())
        return
    elif resource_type == "vk" and "vk.com" not in link:
        await message.answer("❌ Неверная ссылка VK", reply_markup=get_back_to_admin())
        return
    
    # Сохраняем в БД
    try:
        await db.connect()  # Убедимся что БД подключена
        resource_id = await db.add_target_resource(resource_type, link)
        
        await message.answer(
            f"✅ <b>Ресурс добавлен!</b>\n\n"
            f"Тип: {resource_type}\n"
            f"Ссылка: {link}",
            reply_markup=get_admin_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error adding resource: {e}")
        await message.answer(f"❌ Ошибка: {e}", reply_markup=get_back_to_admin())
    
    await state.clear()


@router.callback_query(F.data == "admin_list_resources")
async def admin_list_resources(callback: CallbackQuery):
    """Список ресурсов"""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    
    try:
        await db.connect()
        resources = await db.get_target_resources(active_only=False)
        
        if not resources:
            text = "📋 <b>Список ресурсов</b>\n\nРесурсов пока нет."
        else:
            text = "📋 <b>Список ресурсов</b>\n\n"
            for r in resources:
                status = "✅" if r['is_active'] else "❌"
                text += f"{status} #{r['id']} {r['type']}\n"
                text += f"   {r['link']}\n\n"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="◀️ Админ-панель", callback_data="admin_menu")
        
        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")
    
    await callback.answer()


@router.callback_query(F.data == "admin_keywords")
async def admin_keywords(callback: CallbackQuery):
    """Меню ключевых слов"""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    
    await callback.message.edit_text(
        "🔑 <b>Ключевые слова</b>\n\n"
        "Настройка слов для мониторинга:",
        reply_markup=get_keywords_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_add_keyword")
async def admin_add_keyword(callback: CallbackQuery, state: FSMContext):
    """Добавить ключевое слово"""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    
    await callback.message.edit_text(
        "🔑 <b>Добавить ключевое слово</b>\n\n"
        "Введите слово или фразу:",
        reply_markup=get_back_to_admin(),
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.wait_keyword)
    await callback.answer()


@router.message(AdminStates.wait_keyword)
async def admin_save_keyword(message: Message, state: FSMContext):
    """Сохранение ключевого слова"""
    keyword = message.text.strip()
    
    if len(keyword) < 2:
        await message.answer("❌ Слово слишком короткое", reply_markup=get_back_to_admin())
        return
    
    try:
        await db.connect()
        await db.add_spy_keyword(keyword)
        
        await message.answer(
            f"✅ <b>Ключевое слово добавлено!</b>\n\n"
            f"Слово: {keyword}",
            reply_markup=get_keywords_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Error adding keyword: {e}")
        await message.answer(f"❌ Ошибка: {e}", reply_markup=get_back_to_admin())
    
    await state.clear()


@router.callback_query(F.data == "admin_list_keywords")
async def admin_list_keywords(callback: CallbackQuery):
    """Список ключевых слов"""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    
    try:
        await db.connect()
        keywords = await db.get_spy_keywords(active_only=False)
        
        if not keywords:
            text = "🔑 <b>Ключевые слова</b>\n\nСлов пока нет."
        else:
            text = "🔑 <b>Ключевые слова</b>\n\n"
            for kw in keywords:
                status = "✅" if kw['is_active'] else "❌"
                text += f"{status} #{kw['id']} {kw['keyword']}\n"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="◀️ Назад", callback_data="admin_keywords")
        
        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")
    
    await callback.answer()


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    """Назад - сбрасываем состояние"""
    await state.clear()
    await cmd_admin(callback.message, state)
    await callback.answer()
