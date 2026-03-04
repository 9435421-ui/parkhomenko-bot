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
    wait_lead_reply = State()  # текст ответа лиду от имени Антона
    wait_add_target_link = State()  # /add_target: ожидание ссылки, если не передана в команде


def check_admin(user_id: int) -> bool:
    """Проверка прав администратора"""
    return user_id == ADMIN_ID or (JULIA_USER_ID and user_id == JULIA_USER_ID)


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Главное меню админ-панели"""
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Добавить ресурс", callback_data="admin_add_resource")
    builder.button(text="📋 Список ресурсов", callback_data="admin_list_resources")
    builder.button(text="🔑 Ключевые слова", callback_data="admin_keywords")
    builder.button(text="🕵️ Управление Шпионом", callback_data="admin_spy_panel")
    builder.button(text="◀️ Назад", callback_data="admin_back")
    builder.adjust(1, 1, 1, 1, 1)
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


async def get_spy_panel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура пульта шпиона; переключатель уведомлений по текущей настройке."""
    notify = await db.get_setting("spy_notify_enabled", "1")
    notify_label = "🔔 Уведомления: ВЫКЛ" if notify != "1" else "🔔 Уведомления: ВКЛ"
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика (24ч)", callback_data="spy_panel_stats")
    builder.button(text="📝 Ключевые слова", callback_data="spy_panel_keywords")
    builder.button(text="🌐 Ресурсы", callback_data="spy_panel_resources")
    builder.button(text=notify_label, callback_data="spy_panel_toggle_notify")
    builder.button(text="◀️ В админ-меню", callback_data="admin_menu")
    builder.adjust(1, 1, 1, 1, 1)
    return builder.as_markup()


# === ПУЛЬТ УПРАВЛЕНИЯ ШПИОНОМ (инлайн) ===
@router.callback_query(F.data == "admin_spy_panel")
async def spy_panel_open(callback: CallbackQuery):
    """Открыть пульт управления Шпионом."""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    kb = await get_spy_panel_keyboard()
    await callback.message.edit_text(
        "🕵️ <b>Пульт управления Шпионом</b>\n\n"
        "Выберите действие:",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "spy_panel_stats")
async def spy_panel_stats(callback: CallbackQuery):
    """Статистика за 24ч (логика /spy_status)."""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    try:
        tg_list = [f"📱 {ch['name']} (@{ch['id']})" for ch in scout_parser.TG_CHANNELS]
        vk_list = [f"📘 {g['name']} (id{g['id']})" for g in scout_parser.VK_GROUPS]
        resources = await db.get_target_resources(active_only=True)
        db_list = [f"{'📱' if r['type'] == 'telegram' else '📘'} {r.get('title') or r['link']}" for r in resources]
        lines = [
            "📊 <b>Статистика шпиона (24ч)</b>",
            "",
            "<b>Telegram каналы:</b>",
        ]
        lines.extend(tg_list[:15] or ["— нет"])
        if len(tg_list) > 15:
            lines.append(f"… и ещё {len(tg_list) - 15}")
        lines.append("<b>VK группы:</b>")
        lines.extend(vk_list[:10] or ["— нет"])
        if db_list:
            lines.append("<b>Из админки:</b>")
            lines.extend(db_list[:5])
        count_24h = await db.get_spy_leads_count_24h()
        lines.append("")
        lines.append(f"📊 <b>Лидов за последние 24 ч:</b> {count_24h}")
        kb = await get_spy_panel_keyboard()
        await callback.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        await callback.answer(f"❌ {e}", show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data == "spy_panel_keywords")
async def spy_panel_keywords(callback: CallbackQuery):
    """Список ключевых слов и триггеров."""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    try:
        keywords = await db.get_spy_keywords(active_only=False)
        kws = [kw["keyword"] for kw in keywords] if keywords else []
        # Из кода ScoutParser
        code_kws = list(scout_parser.KEYWORDS)[:25]
        lines = [
            "📝 <b>Ключевые слова</b>",
            "",
            "<b>Из кода (Scout):</b>",
            ", ".join(code_kws) + ("…" if len(scout_parser.KEYWORDS) > 25 else ""),
            "",
        ]
        if kws:
            lines.append("<b>Из админки (БД):</b>")
            lines.append(", ".join(kws[:30]) + ("…" if len(kws) > 30 else ""))
        else:
            lines.append("<b>Из админки:</b> — нет")
        kb = await get_spy_panel_keyboard()
        await callback.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        await callback.answer(f"❌ {e}", show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data == "spy_panel_resources")
async def spy_panel_resources(callback: CallbackQuery):
    """Список чатов/групп в мониторинге."""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    try:
        tg_list = [f"📱 {ch['name']} (@{ch['id']})" for ch in scout_parser.TG_CHANNELS]
        vk_list = [f"📘 {g['name']} (id{g['id']})" for g in scout_parser.VK_GROUPS]
        resources = await db.get_target_resources(active_only=True)
        db_list = [f"{'📱' if r['type'] == 'telegram' else '📘'} {r.get('title') or r['link']}" for r in resources]
        lines = [
            "🌐 <b>Ресурсы в мониторинге</b>",
            "",
            "<b>Telegram (Scout):</b>",
        ]
        lines.extend(tg_list[:18] or ["— нет"])
        if len(tg_list) > 18:
            lines.append(f"… и ещё {len(tg_list) - 18}")
        lines.append("<b>VK (Scout):</b>")
        lines.extend(vk_list[:12] or ["— нет"])
        if db_list:
            lines.append("<b>Админка (target_resources):</b>")
            lines.extend(db_list[:8])
        kb = await get_spy_panel_keyboard()
        await callback.message.edit_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        await callback.answer(f"❌ {e}", show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data == "spy_panel_toggle_notify")
async def spy_panel_toggle_notify(callback: CallbackQuery):
    """Переключатель уведомлений в личку (ВКЛ/ВЫКЛ)."""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    try:
        current = await db.get_setting("spy_notify_enabled", "1")
        new_val = "0" if current == "1" else "1"
        await db.set_setting("spy_notify_enabled", new_val)
        state = "ВКЛ" if new_val == "1" else "ВЫКЛ"
        await callback.answer(f"🔔 Уведомления: {state}")
        kb = await get_spy_panel_keyboard()
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception as e:
        await callback.answer(f"❌ {e}", show_alert=True)


# === КОМАНДА /SPY_STATUS ===
@router.message(Command("spy_status"))
async def cmd_spy_status(message: Message):
    """Статус шпиона: активные чаты/группы мониторинга и кол-во лидов за 24 ч (только для админа)."""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа")
        return
    try:
        # Активные источники: из scout_parser (TG + VK) и из БД (target_resources)
        tg_list = [f"📱 {ch['name']} (@{ch['id']})" for ch in scout_parser.TG_CHANNELS]
        vk_list = [f"📘 {g['name']} (id{g['id']})" for g in scout_parser.VK_GROUPS]
        resources = await db.get_target_resources(active_only=True)
        db_list = [f"{'📱' if r['type'] == 'telegram' else '📘'} {r.get('title') or r['link']}" for r in resources]
        lines = [
            "🕵️ <b>Статус шпиона</b>",
            "",
            "<b>Активные чаты/группы для мониторинга:</b>",
            "<b>Telegram каналы (Scout):</b>",
        ]
        lines.extend(tg_list[:20] or ["— нет"])
        if len(tg_list) > 20:
            lines.append(f"… и ещё {len(tg_list) - 20}")
        lines.append("<b>VK группы (Scout):</b>")
        lines.extend(vk_list[:15] or ["— нет"])
        if len(vk_list) > 15:
            lines.append(f"… и ещё {len(vk_list) - 15}")
        if db_list:
            lines.append("<b>Из админки (target_resources):</b>")
            lines.extend(db_list[:10])
        # Лидов за 24 часа
        count_24h = await db.get_spy_leads_count_24h()
        lines.append("")
        lines.append(f"📊 <b>Собрано лидов за последние 24 ч:</b> {count_24h}")
        await message.answer("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        logger.exception("spy_status")
        await message.answer(f"❌ Ошибка: {e}")


# === КОМАНДА /LEADS_REVIEW (ревизия лидов за ночь) ===
@router.message(Command("leads_review"))
async def cmd_leads_review(message: Message):
    """Ревизия лидов: кто попался за последние 12 ч и какие «боли» озвучили (для утреннего плана)."""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа")
        return
    try:
        leads = await db.get_spy_leads_since_hours(since_hours=12)
        if not leads:
            await message.answer(
                "📋 <b>Ревизия лидов</b> (за последние 12 ч)\n\n"
                "Пока никого не попалось. Запустите /hunt для скана или подождите следующего цикла шпиона.",
                parse_mode="HTML"
            )
            return
        text = (
            "📋 <b>Ревизия лидов</b> (за последние 12 ч)\n\n"
            f"Попалось в сети: <b>{len(leads)}</b>\n\n"
        )
        for i, lead in enumerate(leads[:25], 1):
            who = lead.get("username") or lead.get("author_id") or "—"
            if lead.get("profile_url"):
                who = f'<a href="{lead["profile_url"]}">{who}</a>'
            source = (lead.get("source_name") or lead.get("source_type") or "—").replace("<", "").replace(">", "")
            pain = (lead.get("text") or "").strip().replace("\n", " ")[:200]
            if len(lead.get("text") or "") > 200:
                pain += "…"
            text += f"<b>{i}. {who}</b> · {source}\n{pain}\n\n"
        if len(leads) > 25:
            text += f"… и ещё {len(leads) - 25} лидов."
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        logger.exception("leads_review")
        await message.answer(f"❌ Ошибка: {e}")


# ID с приоритетом для /scan_chats (пускать без очереди)
SCAN_CHATS_PRIORITY_USER_ID = 8438024806

# === КОМАНДА /SCAN_CHATS (сканер диалогов для добычи ID) ===
@router.message(Command("scan_chats"))
async def cmd_scan_chats(message: Message):
    """Пробежаться по всем активным диалогам/чатам Telethon и выдать таблицу: ID, название, участники. Работает во всех топиках группы."""
    user_id = message.from_user.id
    logger.info("scan_chats: команда получена, user_id=%s, chat_id=%s, thread_id=%s", user_id, message.chat.id, getattr(message, "message_thread_id", None))
    print("[/scan_chats] Сигнал дошел до хендлера", flush=True)
    allow = user_id == SCAN_CHATS_PRIORITY_USER_ID or check_admin(user_id)
    if not allow:
        await message.answer("⛔ У вас нет доступа")
        return
    logger.info("Команда /scan_chats опознана для админа %s", user_id)
    await message.answer("⏳ Начинаю сканирование...")
    await message.answer("🔍 Сканирую диалоги и чаты (Telethon)...")
    try:
        chats = await scout_parser.scan_all_chats()
        if not chats:
            await message.answer(
                "📭 Список пуст или Telethon не авторизован. Проверьте API_ID, API_HASH, TELEGRAM_PHONE.",
                parse_mode="HTML"
            )
            return
        lines = [
            "📋 <b>Чаты и диалоги</b> (ID, название, участники)",
            "",
            "ID | Название | Участников | Ссылка",
            "—" * 40,
        ]
        for c in chats[:80]:
            pid = c.get("id", "—")
            title = (c.get("title") or "—").replace("<", "").replace(">", "")[:35]
            n = c.get("participants_count") or "—"
            link = c.get("link", "")
            lines.append(f"{pid} | {title} | {n} | {link}")
        if len(chats) > 80:
            lines.append(f"... и ещё {len(chats) - 80}")
        text = "\n".join(lines)
        if len(text) > 4000:
            from aiogram.types import BufferedInputFile
            file = BufferedInputFile(text.encode("utf-8"), filename="scan_chats.txt")
            await message.answer_document(file, caption=f"📋 Всего чатов/диалогов: {len(chats)}")
        else:
            await message.answer(text, parse_mode="HTML")
        # Кнопка импорта чатов с >500 участников в цели (pending)
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="📥 Импортировать в pending (чаты >500 уч.)", callback_data="import_scan_pending")
        await message.answer(
            "Добавить чаты с числом участников >500 в очередь на утверждение?",
            reply_markup=builder.as_markup(),
        )
    except Exception as e:
        logger.exception("scan_chats")
        await message.answer(f"❌ Ошибка: {e}")


# === КОЛБЭК: ИМПОРТ СКАНА В PENDING ===
@router.callback_query(F.data == "import_scan_pending")
async def cb_import_scan_pending(callback: CallbackQuery):
    """Импорт последнего результата scan_chats (участников >500) в target_resources со статусом pending."""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    chats = getattr(scout_parser, "last_scan_chats_list", None) or []
    if not chats:
        await callback.answer("Нет данных последнего скана. Сначала выполните /scan_chats.")
        return
    try:
        await db.connect()
        n = await db.import_scan_to_target_resources(chats, min_participants=500)
        await callback.message.answer(f"✅ Импортировано целей в pending: {n}. Проверьте /approve_targets.")
    except Exception as e:
        logger.exception("import_scan_pending")
        await callback.message.answer(f"❌ Ошибка импорта: {e}")
    await callback.answer()


# === КОМАНДА /APPROVE_TARGETS ===
@router.message(Command("approve_targets"))
async def cmd_approve_targets(message: Message):
    """Список ресурсов со статусом pending: Название | Участники, кнопки «В работу» / «В архив»."""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа")
        return
    try:
        await db.connect()
        pending = await db.get_pending_targets()
        if not pending:
            await message.answer("📋 Нет ресурсов в очереди (pending). Добавьте через /add_target или импорт после /scan_chats.")
            return
        lines = ["📋 <b>Ресурсы на утверждение</b> (Название | Участников)\n"]
        builder = InlineKeyboardBuilder()
        for r in pending[:30]:
            title = (r.get("title") or r.get("link") or "—")[:40].replace("<", "").replace(">", "")
            pc = r.get("participants_count")
            pc_str = str(pc) if pc is not None else "—"
            lines.append(f"• {title} | {pc_str} уч.")
            builder.row(
                InlineKeyboardButton(text="✅ В работу", callback_data=f"approve_target:{r['id']}:active"),
                InlineKeyboardButton(text="❌ В архив", callback_data=f"approve_target:{r['id']}:archived"),
            )
        builder.row(InlineKeyboardButton(text="◀️ Закрыть", callback_data="admin_menu"))
        await message.answer("\n".join(lines), reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception as e:
        logger.exception("approve_targets")
        await message.answer(f"❌ Ошибка: {e}")


@router.callback_query(F.data.startswith("approve_target:"))
async def cb_approve_target(callback: CallbackQuery):
    """Установить статус ресурса: active или archived."""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Неверный формат")
        return
    try:
        rid = int(parts[1])
        status = parts[2]  # active | archived
        if status not in ("active", "archived"):
            await callback.answer("Неверный статус")
            return
        await db.set_target_status(rid, status)
        label = "в работу" if status == "active" else "в архив"
        await callback.answer(f"✅ Ресурс #{rid} переведён {label}")
        # Обновить сообщение: убрать эту строку или обновить список
        await callback.message.edit_text(
            callback.message.text + f"\n\n✅ #{rid} → {label}",
            reply_markup=callback.message.reply_markup,
        )
    except Exception as e:
        logger.exception("approve_target")
        await callback.answer(f"Ошибка: {e}")


# === КОМАНДА /ADD_TARGET [ссылка] ===
@router.message(Command("add_target"))
async def cmd_add_target(message: Message, state: FSMContext):
    """Вручную добавить ЖК/чат по ссылке. Бот определит ID и сохранит в БД со статусом pending."""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа")
        return
    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)
    link = parts[1].strip() if len(parts) > 1 else None
    if link and "t.me" in link:
        await _do_add_target(message, link, state)
        return
    await state.set_state(AdminStates.wait_add_target_link)
    await message.answer(
        "📎 Отправьте ссылку на Telegram-чат/канал (t.me/...):",
        reply_markup=get_back_to_admin(),
    )


@router.message(AdminStates.wait_add_target_link, F.text)
async def msg_add_target_link(message: Message, state: FSMContext):
    """Обработка ссылки для /add_target."""
    link = (message.text or "").strip()
    if "t.me" not in link:
        await message.answer("❌ Нужна ссылка вида t.me/...", reply_markup=get_back_to_admin())
        return
    await _do_add_target(message, link, state)


async def _do_add_target(message: Message, link: str, state: FSMContext):
    """Разрешить ссылку через Telethon и сохранить в target_resources со статусом pending."""
    await state.clear()
    await message.answer("⏳ Проверяю ссылку...")
    try:
        info = await scout_parser.resolve_telegram_link(link)
        if not info:
            await message.answer("❌ Не удалось определить чат по ссылке. Проверьте ссылку и доступ Антона.", reply_markup=get_back_to_admin())
            return
        await db.connect()
        rid = await db.add_target_resource(
            "telegram",
            info["link"],
            title=info.get("title") or info["link"],
            notes="Добавлено вручную (/add_target)",
            status="pending",
            participants_count=info.get("participants_count"),
        )
        pc = info.get("participants_count")
        pc_str = f", участников: {pc}" if pc is not None else ""
        await message.answer(
            f"✅ Ресурс добавлен в очередь (pending). ID: {rid}{pc_str}\n"
            f"Утвердите через /approve_targets.",
            reply_markup=get_back_to_admin(),
        )
    except Exception as e:
        logger.exception("add_target")
        await message.answer(f"❌ Ошибка: {e}", reply_markup=get_back_to_admin())


# === КОМАНДА /SET_GEO ===
@router.message(Command("set_geo"))
async def cmd_set_geo(message: Message):
    """Установить «человеческое» название ЖК для чата: /set_geo [id или ссылка] [Название ЖК]."""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа")
        return
    parts = (message.text or "").strip().split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "Использование: /set_geo [id или ссылка] [Название ЖК]\n"
            "Примеры:\n• /set_geo 5 ЖК Зиларт\n• /set_geo https://t.me/c/123 ЖК Сердце Столицы"
        )
        return
    link_or_id = parts[1].strip()
    geo_tag = parts[2].strip()
    resource_id = None
    link = None
    if link_or_id.isdigit():
        resource_id = int(link_or_id)
    else:
        link = link_or_id
    try:
        await db.connect()
        ok = await db.set_target_geo(resource_id=resource_id, link=link, geo_tag=geo_tag)
        if ok:
            await message.answer(f"✅ Для ресурса установлено название: <b>{geo_tag}</b>", parse_mode="HTML")
        else:
            await message.answer("❌ Ресурс не найден по указанному id или ссылке.")
    except Exception as e:
        logger.exception("set_geo")
        await message.answer(f"❌ Ошибка: {e}")


# === КОМАНДА /SET_PRIORITY (приоритетный ЖК — высотка) ===
@router.message(Command("set_priority"))
async def cmd_set_priority(message: Message):
    """Пометить чат как приоритетный ЖК (высотка): /set_priority [id или ссылка] [1|0]."""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа")
        return
    parts = (message.text or "").strip().split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "Использование: /set_priority [id или ссылка] [1|0]\n"
            "1 — приоритетный ЖК (высотка), 0 — снять пометку.\n"
            "Пример: /set_priority 5 1"
        )
        return
    link_or_id = parts[1].strip()
    try:
        is_high = int(parts[2].strip()) != 0
    except ValueError:
        await message.answer("❌ Третий аргумент: 1 или 0.")
        return
    resource_id = None
    link = None
    if link_or_id.isdigit():
        resource_id = int(link_or_id)
    else:
        link = link_or_id
    try:
        await db.connect()
        ok = await db.set_target_high_priority(resource_id=resource_id, link=link, is_high=is_high)
        if ok:
            label = "приоритетный ЖК (Высотка)" if is_high else "снята пометка «Высотка»"
            await message.answer(f"✅ Ресурс: <b>{label}</b>", parse_mode="HTML")
        else:
            await message.answer("❌ Ресурс не найден по указанному id или ссылке.")
    except Exception as e:
        logger.exception("set_priority")
        await message.answer(f"❌ Ошибка: {e}")


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


# === КОМАНДА /SPY_DISCOVER (ручная разведка / добавление новых целей) ===
@router.message(Command("spy_discover"))
async def cmd_spy_discover(message: Message):
    """Запустить автоматическую разведку новых чатов/групп (использует services.lead_hunter.Discovery)."""
    if not check_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа")
        return
    await message.answer("🔎 Запускаю разведку новых источников...")
    try:
        from services.lead_hunter import Discovery
        disc = Discovery()
        keywords = disc.get_keywords()
        results = await disc.find_new_sources()
        if not results:
            await message.answer("📭 Ничего не найдено.")
            return
        await db.connect()
        added = 0
        for r in results:
            link = (r.get("link") or "").strip()
            if not link:
                continue
            title = r.get("title") or link
            participants = r.get("participants_count")
            # Сохраняем как active — админство может откорректировать статус позже
            await db.add_target_resource("telegram", link, title=title, participants_count=participants, status="active")
            added += 1
        await message.answer(f"✅ Разведка завершена. Добавлено/обновлено ресурсов: {added}")
    except Exception as e:
        logger.exception("spy_discover")
        await message.answer(f"❌ Ошибка разведки: {e}")

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


# === ОТВЕТ ЭКСПЕРТНО (Агент-Антон, до 500 знаков + дисклеймер + квиз) ===
@router.callback_query(F.data.startswith("lead_expert_reply_"))
async def lead_expert_reply(callback: CallbackQuery):
    """Кнопка «Ответить экспертно»: генерация ответа через Агента-Антона (Retrieval), отправка лиду в ЛС."""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    try:
        lead_id = int(callback.data.replace("lead_expert_reply_", ""))
    except ValueError:
        await callback.answer("❌ Неверный ID лида")
        return
    lead = await db.get_spy_lead(lead_id)
    if not lead:
        await callback.answer("❌ Лид не найден")
        return
    await callback.answer("⏳ Генерирую ответ через Антона...")
    context = (lead.get("text") or lead.get("url") or "")[:2000]
    try:
        from utils.yandex_ai_agents import call_anton_agent
        reply = await call_anton_agent(context, max_chars=500)
    except Exception as e:
        reply = f"Произошла ошибка при генерации ответа. Ответьте лиду вручную. ({e})"
    author_id = lead.get("author_id")
    source_type = lead.get("source_type", "telegram")
    if source_type == "telegram" and author_id:
        try:
            await callback.bot.send_message(int(author_id), reply, parse_mode="HTML")
            await callback.message.answer("✅ Экспертный ответ отправлен лиду в ЛС.")
        except Exception as e:
            await callback.message.answer(f"❌ Не удалось отправить в ЛС: {e}. Скопируйте текст и ответьте вручную:\n\n{reply[:500]}")
    else:
        await callback.message.answer(f"📋 Ответ (отправьте лиду вручную):\n\n{reply}")


# === ВЗЯТЬ В РАБОТУ (контакт Юлии в личку лиду) ===
@router.callback_query(F.data.startswith("lead_take_work_"))
async def lead_take_work(callback: CallbackQuery):
    """Кнопка «Взять в работу»: пересылает контакт Юлии лиду в личку."""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    try:
        lead_id = int(callback.data.replace("lead_take_work_", ""))
    except ValueError:
        await callback.answer("❌ Неверный ID лида")
        return
    lead = await db.get_spy_lead(lead_id)
    if not lead:
        await callback.answer("❌ Лид не найден")
        return
    from config import JULIA_CONTACT
    author_id = lead.get("author_id")
    if lead.get("source_type") == "telegram" and author_id:
        try:
            await callback.bot.send_message(int(author_id), f"🛠 Взят в работу.\n\n{JULIA_CONTACT}", parse_mode="HTML")
            await callback.answer("✅ Контакт Юлии отправлен лиду.")
        except Exception as e:
            await callback.answer()
            await callback.message.answer(f"❌ Не удалось отправить: {e}. Напишите лиду вручную: {JULIA_CONTACT}")
    else:
        await callback.answer()
        await callback.message.answer(f"Отправьте лиду вручную: {JULIA_CONTACT}")


# === ОТВЕТ ЛИДУ ОТ ИМЕНИ АНТОНА (ручной ввод текста) ===
@router.callback_query(F.data.startswith("lead_reply_"))
async def lead_reply_start(callback: CallbackQuery, state: FSMContext):
    """По нажатию «🤖 Ответить от имени Антона» — запрашиваем текст ответа."""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    try:
        lead_id = int(callback.data.replace("lead_reply_", ""))
    except ValueError:
        await callback.answer("❌ Неверный ID лида")
        return
    lead = await db.get_spy_lead(lead_id)
    if not lead:
        await callback.answer("❌ Лид не найден")
        return
    await state.set_state(AdminStates.wait_lead_reply)
    await state.update_data(lead_reply_id=lead_id)
    await callback.message.answer(
        f"🤖 <b>Ответ лиду #{lead_id}</b>\n\n"
        f"📄 Текст лида: {(lead.get('text') or '')[:200]}…\n\n"
        "Введите текст ответа от имени Антона (будет отправлен в ЛС, если лид уже писал боту). Или /cancel для отмены.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(AdminStates.wait_lead_reply, F.text)
async def lead_reply_text(message: Message, state: FSMContext):
    """Отправка введённого текста лиду (Telegram)."""
    if not check_admin(message.from_user.id):
        return
    if message.text and message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("Отменено.")
        return
    data = await state.get_data()
    lead_id = data.get("lead_reply_id")
    if not lead_id:
        await state.clear()
        return
    lead = await db.get_spy_lead(lead_id)
    if not lead:
        await state.clear()
        await message.answer("Лид не найден.")
        return
    author_id = lead.get("author_id")
    source_type = lead.get("source_type", "telegram")
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст не должен быть пустым. Введите снова или /cancel.")
        return
    await state.clear()
    if source_type != "telegram" or not author_id:
        await message.answer(
            f"❌ Отправить в ЛС можно только по Telegram (author_id есть у лида). У этого лида source_type={source_type}, author_id={author_id}. "
            "Скопируйте текст и ответьте вручную."
        )
        return
    try:
        await message.bot.send_message(int(author_id), text)
        await message.answer("✅ Сообщение отправлено лиду в ЛС.")
    except Exception as e:
        await message.answer(
            f"❌ Не удалось отправить: {e}. Возможно, лид ещё не писал боту — тогда напишите ему вручную (профиль в карточке)."
        )


# === ПУБЛИКАЦИЯ ИНСАЙТА В MAX ===
@router.callback_query(F.data.startswith("publish_insight_max_"))
async def cb_publish_insight_max(callback: CallbackQuery):
    """Публикация подготовленного инсайта в канал MAX."""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return

    try:
        lead_id = int(callback.data.replace("publish_insight_max_", ""))
    except ValueError:
        await callback.answer("❌ Неверный ID")
        return

    # Ищем черновик инсайта для этого лида
    async with db.conn.execute(
        "SELECT * FROM content_plan WHERE admin_id = ? AND type = 'insight' AND status = 'draft' ORDER BY created_at DESC LIMIT 1",
        (lead_id,)
    ) as cursor:
        row = await cursor.fetchone()
        post = dict(row) if row else None

    if not post:
        await callback.answer("❌ Черновик не найден или уже опубликован", show_alert=True)
        return

    await callback.answer("🚀 Публикую в MAX.ru...")

    from services.publisher import publisher
    success = await publisher.publish_to_max(post['body'], title="💡 Инсайт TERION")

    if success:
        await db.update_content_plan_entry(post['id'], status='published', published_at=datetime.now())
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply("✅ Инсайт успешно опубликован в MAX.ru!")
    else:
        await callback.message.reply("❌ Ошибка при публикации в MAX. Проверьте логи.")
