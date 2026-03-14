"""
Admin Panel — управление ресурсами и ключевыми словами.
Команда: /admin
<<<<<<< HEAD
aiogram 3.x версия
"""
from aiogram import Router, F, Dispatcher
=======
"""
from aiogram import Router, F, Bot
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
<<<<<<< HEAD
import logging

from database import db
from config import ADMIN_ID, JULIA_USER_ID
from services.lead_hunter.discovery import Discovery
from services.scout_parser import ScoutParser

logger = logging.getLogger(__name__)
admin_router = Router()
=======
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

from database import db
from config import (
    ADMIN_ID, JULIA_USER_ID, NOTIFICATIONS_CHANNEL_ID, THREAD_ID_LOGS,
    LEADS_GROUP_CHAT_ID, THREAD_ID_DRAFTS, BOT_TOKEN,
)
from services.scout_parser import scout_parser

logger = logging.getLogger(__name__)
router = Router()
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377


class AdminStates(StatesGroup):
    wait_resource_link = State()
    wait_keyword = State()
<<<<<<< HEAD
=======
    wait_lead_reply = State()
    wait_add_target_link = State()
    wait_draft_edit_text = State()  # редактирование черновика из рабочей группы
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377


def check_admin(user_id: int) -> bool:
    """Проверка прав администратора"""
<<<<<<< HEAD
    if user_id == ADMIN_ID:
        return True
    if JULIA_USER_ID and JULIA_USER_ID != 0 and user_id == JULIA_USER_ID:
        return True
    return False


def get_admin_keyboard():
    """Главное меню админ-панели"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Запустить поиск/шпиона", callback_data="admin_run_spy")],
        [InlineKeyboardButton(text="➕ Добавить ресурс", callback_data="admin_add_resource")],
        [InlineKeyboardButton(text="📋 Список ресурсов", callback_data="admin_list_resources")],
        [InlineKeyboardButton(text="🔑 Ключевые слова", callback_data="admin_keywords")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")],
    ])
    return kb


@admin_router.message(Command("admin"))
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


@admin_router.callback_query(F.data == "admin_menu")
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


@admin_router.callback_query(F.data == "admin_run_spy")
async def admin_run_spy(callback: CallbackQuery):
    """Принудительный запуск Discovery и Scout-Parser"""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await callback.message.answer("🚀 Запуск модулей Discovery и Scout-Parser...")
    
    try:
        # Запуск Discovery
        discovery = Discovery()
        new_resources = await discovery.discover_new_resources()
        await callback.message.answer(f"✅ Discovery завершен. Найдено новых ресурсов: {len(new_resources)}")
        
        # Запуск Scout-Parser
        scout = ScoutParser()
        # В ScoutParser обычно есть метод для запуска сканирования, например run_scan или аналогичный
        # Предположим, что мы запускаем его через hunter или напрямую если есть метод
        from services.lead_hunter.hunter import LeadHunter
        hunter = LeadHunter()
        await hunter.hunt()
        await callback.message.answer("✅ Scout-Parser (LeadHunter) завершил поиск лидов.")
        
    except Exception as e:
        logger.error(f"Ошибка при ручном запуске шпиона: {e}")
        await callback.message.answer(f"❌ Ошибка при запуске: {e}")
=======
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


# ============================================================
# === ЧЕРНОВИКИ → РАБОЧАЯ ГРУППА (полный цикл публикации) ===
# ============================================================

_DRAFT_POST_SYSTEM = (
    "Ты — контент-редактор компании TERION (перепланировки квартир в Москве).\n"
    "Напиши экспертный пост для Telegram-канала по заданной теме.\n"
    "Структура: яркий заголовок → суть → польза для читателя → лёгкий призыв к действию.\n"
    "Объём: 150–200 слов. Тон: уверенный, живой, без канцелярита.\n"
    "ЗАПРЕЩЕНО добавлять хештеги и ссылки — они добавятся автоматически при публикации."
)


def get_draft_card_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """Кнопки карточки новой темы в рабочей группе."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✍️ Написать пост", callback_data=f"draft_gen:{post_id}")
    builder.button(text="❌ Удалить тему", callback_data=f"draft_del:{post_id}")
    builder.adjust(1)
    return builder.as_markup()


def get_draft_preview_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """Кнопки превью поста: публикация, редактура, удаление."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Опубликовать", callback_data=f"draft_pub:{post_id}")
    builder.button(text="✏️ Редактировать", callback_data=f"draft_edit:{post_id}")
    builder.button(text="❌ Удалить", callback_data=f"draft_del:{post_id}")
    builder.adjust(2, 1)
    return builder.as_markup()


async def send_draft_to_group(bot, post_id: int, title: str, insight: str) -> None:
    """Отправляет карточку новой темы в топик «Черновики» рабочей группы."""
    text = (
        f"📋 <b>Новая тема в контент-плане</b>\n\n"
        f"<b>{title}</b>\n\n"
        f"💡 {insight}\n\n"
        f"<i>Нажмите «Написать пост», чтобы AI создал текст и обложку</i>"
    )
    try:
        await bot.send_message(
            LEADS_GROUP_CHAT_ID,
            text,
            message_thread_id=THREAD_ID_DRAFTS,
            reply_markup=get_draft_card_keyboard(post_id),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning("send_draft_to_group: %s", e)


@router.callback_query(F.data.startswith("draft_gen:"))
async def draft_gen_post_handler(callback: CallbackQuery):
    """Генерация поста из темы черновика: AI текст + автообложка → превью в группе."""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    try:
        post_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Неверный ID")
        return

    post = await db.get_content_post(post_id)
    if not post:
        await callback.answer("❌ Черновик не найден в базе")
        return

    await callback.answer("⏳ Генерирую...")
    await callback.message.edit_text(
        f"⏳ <b>Пишу пост...</b>\n\n<i>{(post.get('title') or '')[:120]}</i>",
        parse_mode="HTML",
    )

    title = (post.get("title") or "").strip()
    body = (post.get("body") or title).strip()

    post_text = None
    error_message = None
    
    try:
        # Используем локальный RouterAIClient из handlers/content.py
        from handlers.content import router_ai
        post_text = await router_ai.generate(
            prompt=f"Напиши экспертный пост для Telegram-канала TERION на тему:\n«{title}»\n\nКонтекст: {body[:400]}",
            system_prompt=_DRAFT_POST_SYSTEM,
            max_tokens=2000,  # Увеличено до 2000
        )
    except Exception as e:
        error_message = str(e)
        logger.error("draft_gen: router_ai error: %s", e)
        # Отправляем ошибку в топик "Логи"
        try:
            from aiogram import Bot
            from aiogram.client.default import DefaultBotProperties
            bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
            await bot.send_message(
                LEADS_GROUP_CHAT_ID,
                f"⚠️ <b>Ошибка нейросети</b>\n\n"
                f"Тема: <code>{title[:100]}</code>\n"
                f"Ошибка: <code>{error_message[:500]}</code>",
                message_thread_id=THREAD_ID_LOGS,
            )
            await bot.session.close()
        except Exception as notify_err:
            logger.error("Не удалось отправить ошибку в топик: %s", notify_err)

    if not post_text:
        # Возвращаем кнопки публикации даже при ошибке
        await callback.message.edit_text(
            f"⚠️ <b>Не удалось сгенерировать текст</b>\n\n"
            f"Тема: <code>{title[:100]}</code>\n"
            f"{f'Ошибка: {error_message[:200]}' if error_message else 'Попробуйте ещё раз.'}",
            reply_markup=get_draft_card_keyboard(post_id),
            parse_mode="HTML",
        )
        return

    await db.update_content_plan_entry(post_id, body=post_text)

    # Генерация обложки
    status_msg = await callback.message.answer("🎨 <b>Генерирую обложку...</b>", parse_mode="HTML")
    image_file_id = None
    try:
        import base64
        from aiogram.types import BufferedInputFile
        from handlers.content import _build_cover_prompt, _auto_generate_image

        img_prompt = _build_cover_prompt(post_text)
        image_b64 = await _auto_generate_image(img_prompt)
        await status_msg.delete()

        if image_b64:
            image_bytes = base64.b64decode(image_b64)
            photo = BufferedInputFile(image_bytes, filename="draft_preview.jpg")
            sent = await callback.message.answer_photo(
                photo=photo,
                caption=f"📝 <b>Превью поста</b>\n\n{post_text[:900]}",
                parse_mode="HTML",
                reply_markup=get_draft_preview_keyboard(post_id),
            )
            image_file_id = sent.photo[-1].file_id
            await db.update_content_plan_entry(post_id, image_url=image_file_id)
            await callback.message.delete()
            return
    except Exception as e:
        logger.warning("draft_gen: image error: %s", e)
        try:
            await status_msg.delete()
        except Exception:
            pass

    await callback.message.edit_text(
        f"📝 <b>Превью поста</b>\n\n{post_text[:1200]}",
        parse_mode="HTML",
        reply_markup=get_draft_preview_keyboard(post_id),
    )


@router.callback_query(F.data.startswith("draft_pub:"))
async def draft_pub_handler(callback: CallbackQuery):
    """Публикация черновика во все каналы (TG + VK + MAX)."""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    try:
        post_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Неверный ID")
        return

    post = await db.get_content_post(post_id)
    if not post:
        await callback.answer("❌ Черновик не найден")
        return

    await callback.answer("📤 Публикую...")

    body = (post.get("body") or "").strip()
    title = (post.get("title") or "").strip()
    text = f"<b>{title}</b>\n\n{body}" if title and title not in body else body

    # Добавляем квиз и хештеги
    try:
        from handlers.content import ensure_quiz_and_hashtags
        text = ensure_quiz_and_hashtags(text)
    except Exception:
        from config import VK_QUIZ_LINK, CONTENT_HASHTAGS
        if VK_QUIZ_LINK not in text:
            text += f"\n\n📍 <a href='{VK_QUIZ_LINK}'>Пройти квиз</a>\n{CONTENT_HASHTAGS}"

    # Загружаем изображение, если оно есть
    image_bytes = None
    image_url = post.get("image_url")
    if image_url:
        if not image_url.startswith("http"):
            # Telegram file_id — скачиваем через бот
            try:
                file = await callback.bot.get_file(image_url)
                file_path = file.file_path
                file_url = f"https://api.telegram.org/file/bot{callback.bot.token}/{file_path}"
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(file_url) as resp:
                        if resp.status == 200:
                            image_bytes = await resp.read()
            except Exception as e:
                logger.warning("draft_pub: tg file download: %s", e)
        else:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as resp:
                        if resp.status == 200:
                            image_bytes = await resp.read()
            except Exception as e:
                logger.warning("draft_pub: url download: %s", e)

    from services.publisher import publisher
    results = await publisher.publish_all(text, image_bytes)
    await db.mark_as_published(post_id)

    success = sum(1 for r in results.values() if r)
    channels_str = ", ".join(k for k, v in results.items() if v)
    result_text = (
        f"✅ <b>Опубликовано!</b>\n\n"
        f"Каналы: {channels_str or '—'}\n"
        f"Успешно: {success}/{len(results)}"
    )
    try:
        if callback.message.photo:
            await callback.message.edit_caption(result_text, parse_mode="HTML")
        else:
            await callback.message.edit_text(result_text, parse_mode="HTML")
    except Exception:
        await callback.message.answer(result_text, parse_mode="HTML")


@router.callback_query(F.data.startswith("draft_edit:"))
async def draft_edit_handler(callback: CallbackQuery, state: FSMContext):
    """Запрашивает новый текст для черновика."""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    try:
        post_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Неверный ID")
        return

    await state.set_state(AdminStates.wait_draft_edit_text)
    await state.update_data(draft_edit_post_id=post_id)
    await callback.answer()
    await callback.message.answer(
        f"✏️ <b>Редактирование поста #{post_id}</b>\n\n"
        "Отправьте новый текст одним сообщением — он заменит текущий.\n"
        "/cancel для отмены.",
        parse_mode="HTML",
    )


@router.message(AdminStates.wait_draft_edit_text, F.text)
async def draft_edit_text_handler(message: Message, state: FSMContext):
    """Сохраняет отредактированный текст и показывает кнопки действий."""
    if not check_admin(message.from_user.id):
        return
    if (message.text or "").strip().lower() == "/cancel":
        await state.clear()
        await message.answer("Отменено.")
        return
    data = await state.get_data()
    post_id = data.get("draft_edit_post_id")
    if not post_id:
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("Текст не может быть пустым. Введите снова или /cancel.")
        return
    await db.update_content_plan_entry(post_id, body=text)
    await state.clear()
    await message.answer(
        f"✅ <b>Текст обновлён (пост #{post_id})</b>",
        parse_mode="HTML",
        reply_markup=get_draft_preview_keyboard(post_id),
    )


@router.callback_query(F.data.startswith("draft_del:"))
async def draft_del_handler(callback: CallbackQuery):
    """Удаляет (отклоняет) черновик."""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    try:
        post_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Неверный ID")
        return
    try:
        await db.update_content_post(post_id, status="rejected")
        await callback.answer("🗑 Черновик удалён")
        deleted_text = "🗑 <i>Тема удалена из плана</i>"
        if callback.message.photo:
            await callback.message.edit_caption(deleted_text, parse_mode="HTML")
        else:
            await callback.message.edit_text(deleted_text, parse_mode="HTML")
    except Exception as e:
        await callback.answer(f"❌ {e}")


@router.callback_query(F.data.startswith("lead_to_content:"))
async def lead_to_content_handler(callback: CallbackQuery):
    """Создаёт черновик контент-темы из карточки лида и уведомляет в THREAD_ID_DRAFTS."""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    try:
        lead_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Неверный ID")
        return

    lead = await db.get_spy_lead(lead_id)
    if not lead:
        await callback.answer("❌ Лид не найден")
        return

    # Формируем тему из боли лида
    pain = (lead.get("text") or "").strip()[:300]
    intent = (lead.get("intent") or "").strip()
    geo = (lead.get("geo") or "").strip()
    title = f"Экспертный разбор: {intent or 'перепланировка'}"
    if geo:
        title += f" ({geo})"
    body = f"Боль клиента: {pain}" if pain else title

    post_id = await db.add_content_post(
        title=title,
        body=body,
        cta="Записаться на консультацию",
        channel="terion",
        status="draft",
    )
    await callback.answer(f"📋 Тема сохранена в черновики #{post_id}")
    await send_draft_to_group(callback.bot, post_id, title, intent or pain[:150])


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
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
    
    await callback.answer()


<<<<<<< HEAD
def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков админ-панели"""
    dp.include_router(admin_router)
=======
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
    """Кнопка «В работу»: обновляет статус лида в БД и пересылает контакт Юлии лиду в личку."""
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
    
    # ── ОБНОВЛЕНИЕ СТАТУСА В БД ────────────────────────────────────────────────────
    try:
        await db.mark_lead_in_work(lead_id)
        logger.info(f"✅ Лид #{lead_id} помечен как 'в работе'")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось обновить статус лида #{lead_id}: {e}")
    
    from config import JULIA_CONTACT
    author_id = lead.get("author_id")
    if lead.get("source_type") == "telegram" and author_id:
        try:
            await callback.bot.send_message(int(author_id), f"🛠 Взят в работу.\n\n{JULIA_CONTACT}", parse_mode="HTML")
            await callback.answer("✅ Контакт Юлии отправлен лиду. Статус обновлен.")
        except Exception as e:
            await callback.answer()
            await callback.message.answer(f"❌ Не удалось отправить: {e}. Напишите лиду вручную: {JULIA_CONTACT}")
    else:
        await callback.answer("✅ Статус обновлен. Отправьте лиду вручную.")
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


# ============================================================
# === РЕЖИМ МОДЕРАЦИИ: Обработчики кнопок модерации лидов ===
# ============================================================

class ModerationStates(StatesGroup):
    wait_mod_edit_text = State()  # Редактирование ответа перед отправкой
    wait_mod_approve_confirm = State()  # Подтверждение отправки сгенерированного ответа


@router.callback_query(F.data.startswith("mod_approve_"))
async def mod_approve_handler(callback: CallbackQuery, state: FSMContext):
    """
    Кнопка «✅ Одобрить (Антон пишет ответ)»:
    1. Генерирует ответ через Router AI (Yandex GPT)
    2. Показывает ответ на финальное подтверждение
    3. После подтверждения отправляет лиду
    """
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    try:
        lead_id = int(callback.data.replace("mod_approve_", ""))
    except ValueError:
        await callback.answer("❌ Неверный ID лида")
        return
    
    # Получаем данные лида из БД
    lead = await db.get_spy_lead(lead_id)
    if not lead:
        await callback.answer("❌ Лид не найден")
        return
    
    await callback.answer("⏳ Генерирую ответ через Router AI...")
    
    # Получаем данные для генерации ответа
    post_text = (lead.get("text") or "")[:400]
    source_type = lead.get("source_type", "telegram")
    
    # Получаем данные анализа лида (если есть в БД)
    pain_stage = lead.get("pain_stage", "ST-2")
    intent = lead.get("intent", "")
    context_summary = lead.get("context_summary", "")
    
    # Извлекаем название ЖК из source_name или geo_tag
    source_name = lead.get("source_name", "")
    geo_tag = lead.get("geo_tag", "")
    zhk_name = geo_tag or ""
    if not zhk_name and source_name:
        # Пытаемся извлечь название ЖК из source_name
        import re
        zhk_match = re.search(r"ЖК\s+([А-Яа-яЁё\w\s]+)", source_name, re.IGNORECASE)
        if zhk_match:
            zhk_name = zhk_match.group(1).strip()
    
    # Получаем данные о приоритете ЖК из БД (если есть source_link)
    is_priority_zhk = False
    source_link = lead.get("url", "")
    if source_link:
        try:
            # Пытаемся найти target ресурс по URL поста
            # Для этого нужно извлечь базовую ссылку канала из URL поста
            import re
            if source_type == "telegram":
                # Извлекаем username канала из URL типа https://t.me/channel_name/123
                match = re.search(r't\.me/([^/]+)', source_link)
                if match:
                    channel_username = match.group(1)
                    target_res = await db.get_target_resource_by_link(f"https://t.me/{channel_username}")
                    if target_res:
                        is_priority_zhk = target_res.get("is_high_priority", 0) == 1
            elif source_type == "vk":
                # Извлекаем ID группы из URL типа https://vk.com/wall-123456_789
                match = re.search(r'vk\.com/wall(-?\d+)', source_link)
                if match:
                    group_id = match.group(1)
                    target_res = await db.get_target_resource_by_link(f"https://vk.com/public{group_id.replace('-', '')}")
                    if target_res:
                        is_priority_zhk = target_res.get("is_high_priority", 0) == 1
        except Exception as e:
            logger.debug(f"Не удалось получить данные о приоритете ЖК: {e}")
    
    # Генерируем ответ через Router AI (используем метод из hunter.py с fallback)
    try:
        from services.lead_hunter.hunter import LeadHunter
        hunter = LeadHunter()
        generated_reply = await hunter._generate_sales_reply(
            post_text=post_text,
            pain_stage=pain_stage,
            zhk_name=zhk_name,
            intent=intent,
            context_summary=context_summary,
            platform=source_type,
            is_priority_zhk=is_priority_zhk,
        )
    except Exception as e:
        logger.error(f"Ошибка генерации ответа через Router AI: {e}")
        generated_reply = (
            "Здравствуйте! Вижу ваш вопрос по перепланировке. "
            "TERION специализируется на согласовании перепланировок в Москве. "
            "Могу помочь с проектом и согласованием. Напишите: @terion_expert"
        )
    
    # Сохраняем сгенерированный ответ в состояние для подтверждения
    await state.set_state(ModerationStates.wait_mod_approve_confirm)
    await state.update_data(
        mod_lead_id=lead_id,
        mod_reply_text=generated_reply,
        mod_source_type=source_type,
        mod_author_id=lead.get("author_id"),
    )
    
    # Показываем сгенерированный ответ на подтверждение
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    confirm_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить лиду", callback_data=f"mod_confirm_send_{lead_id}"),
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"mod_edit_{lead_id}"),
        ],
        [
            InlineKeyboardButton(text="❌ Отменить", callback_data=f"mod_cancel_{lead_id}"),
        ],
    ])
    
    await callback.message.answer(
        f"🤖 <b>Ответ сгенерирован через Router AI</b>\n\n"
        f"📄 <b>Текст лида:</b> «{post_text[:200]}{'…' if len(post_text) > 200 else ''}»\n\n"
        f"💬 <b>Ответ Антона:</b>\n\n"
        f"<code>{generated_reply}</code>\n\n"
        f"Выберите действие:",
        parse_mode="HTML",
        reply_markup=confirm_keyboard,
    )


@router.callback_query(F.data.startswith("mod_confirm_send_"))
async def mod_confirm_send_handler(callback: CallbackQuery, state: FSMContext):
    """Подтверждение отправки сгенерированного ответа лиду"""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    try:
        lead_id = int(callback.data.replace("mod_confirm_send_", ""))
    except ValueError:
        await callback.answer("❌ Неверный ID лида")
        return
    
    data = await state.get_data()
    if data.get("mod_lead_id") != lead_id:
        await callback.answer("❌ Несоответствие данных")
        return
    
    reply_text = data.get("mod_reply_text", "")
    source_type = data.get("mod_source_type", "telegram")
    author_id = data.get("mod_author_id")
    
    await state.clear()
    
    # Отправляем ответ лиду
    if source_type == "telegram" and author_id:
        try:
            await callback.bot.send_message(int(author_id), reply_text)
            await callback.answer("✅ Ответ отправлен лиду в ЛС")
            await callback.message.edit_text(
                callback.message.text + "\n\n✅ <b>Ответ отправлен лиду</b>",
                parse_mode="HTML",
            )
        except Exception as e:
            await callback.answer("❌ Ошибка отправки")
            await callback.message.answer(
                f"❌ Не удалось отправить в ЛС: {e}\n\n"
                f"Скопируйте текст и ответьте вручную:\n\n"
                f"<code>{reply_text}</code>",
                parse_mode="HTML",
            )
    else:
        await callback.answer("✅ Готово")
        await callback.message.answer(
            f"📋 <b>Ответ (отправьте лиду вручную):</b>\n\n"
            f"<code>{reply_text}</code>",
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("mod_edit_"))
async def mod_edit_handler(callback: CallbackQuery, state: FSMContext):
    """Кнопка «✏️ Редактировать»: переход в режим ручного редактирования ответа"""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    try:
        lead_id = int(callback.data.replace("mod_edit_", ""))
    except ValueError:
        await callback.answer("❌ Неверный ID лида")
        return
    
    lead = await db.get_spy_lead(lead_id)
    if not lead:
        await callback.answer("❌ Лид не найден")
        return
    
    # Проверяем, есть ли уже сгенерированный ответ в состоянии
    data = await state.get_data()
    current_reply = data.get("mod_reply_text", "")
    
    await state.set_state(ModerationStates.wait_mod_edit_text)
    await state.update_data(
        mod_lead_id=lead_id,
        mod_source_type=lead.get("source_type", "telegram"),
        mod_author_id=lead.get("author_id"),
    )
    
    post_text = (lead.get("text") or "")[:200]
    
    if current_reply:
        await callback.message.answer(
            f"✏️ <b>Редактирование ответа для лида #{lead_id}</b>\n\n"
            f"📄 Текст лида: «{post_text}…»\n\n"
            f"Текущий ответ:\n<code>{current_reply}</code>\n\n"
            f"Введите новый текст ответа или /cancel для отмены.",
            parse_mode="HTML",
        )
    else:
        await callback.message.answer(
            f"✏️ <b>Ручной ввод ответа для лида #{lead_id}</b>\n\n"
            f"📄 Текст лида: «{post_text}…»\n\n"
            f"Введите текст ответа от имени Антона или /cancel для отмены.",
            parse_mode="HTML",
        )
    
    await callback.answer()


@router.message(ModerationStates.wait_mod_edit_text, F.text)
async def mod_edit_text_handler(message: Message, state: FSMContext):
    """Обработка введённого текста ответа (ручное редактирование)"""
    if not check_admin(message.from_user.id):
        return
    
    if message.text and message.text.strip().lower() == "/cancel":
        await state.clear()
        await message.answer("Отменено.")
        return
    
    data = await state.get_data()
    lead_id = data.get("mod_lead_id")
    if not lead_id:
        await state.clear()
        return
    
    edited_reply = (message.text or "").strip()
    if not edited_reply:
        await message.answer("Текст не должен быть пустым. Введите снова или /cancel.")
        return
    
    source_type = data.get("mod_source_type", "telegram")
    author_id = data.get("mod_author_id")
    
    await state.clear()
    
    # Отправляем отредактированный ответ лиду
    if source_type == "telegram" and author_id:
        try:
            await message.bot.send_message(int(author_id), edited_reply)
            await message.answer("✅ Отредактированный ответ отправлен лиду в ЛС.")
        except Exception as e:
            await message.answer(
                f"❌ Не удалось отправить: {e}\n\n"
                f"Скопируйте текст и ответьте вручную:\n\n"
                f"<code>{edited_reply}</code>",
                parse_mode="HTML",
            )
    else:
        await message.answer(
            f"📋 <b>Ответ (отправьте лиду вручную):</b>\n\n"
            f"<code>{edited_reply}</code>",
            parse_mode="HTML",
        )


@router.callback_query(F.data.startswith("mod_skip_"))
async def mod_skip_handler(callback: CallbackQuery):
    """Кнопка «🗑 Пропустить»: просто отмечает лид как пропущенный"""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    try:
        lead_id = int(callback.data.replace("mod_skip_", ""))
    except ValueError:
        await callback.answer("❌ Неверный ID лида")
        return
    
    # Можно добавить обновление статуса в БД (например, status = 'skipped')
    # Пока просто подтверждаем действие
    await callback.answer("✅ Лид пропущен")
    await callback.message.edit_text(
        callback.message.text + "\n\n🗑 <b>Пропущен</b>",
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("mod_cancel_"))
async def mod_cancel_handler(callback: CallbackQuery, state: FSMContext):
    """Отмена действия модерации"""
    if not check_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    await state.clear()
    await callback.answer("❌ Действие отменено")
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
