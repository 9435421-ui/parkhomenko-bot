"""
Admin Panel — управление ресурсами и ключевыми словами.
Команда: /admin
aiogram 3.x версия
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from keyboards.admin_kb import get_admin_main_menu # Предполагаем, что она там
from agents.content_agent import content_agent

router = Router()


class AdminStates(StatesGroup):
    waiting_for_voice = State()


# Проверка прав администратора
# (оставляем как есть, но удаляем из кода)


def get_admin_keyboard():
    """Главное меню админ-панели"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎙 Записать мысль", callback_data="admin:interview")],
        [InlineKeyboardButton(text="🚀 Запустить поиск/шпиона", callback_data="admin_run_spy")],
        [InlineKeyboardButton(text="➕ Добавить ресурс", callback_data="admin_add_resource")],
        [InlineKeyboardButton(text="📋 Список ресурсов", callback_data="admin_list_resources")],
        [InlineKeyboardButton(text="🔑 Ключевые слова", callback_data="admin_keywords")],
        [InlineKeyboardButton(text="🗓 Сгенерировать план на неделю", callback_data="admin_generate_plan")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_back")],
    ])
    return kb


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Главная команда админ-панели"""
    await message.answer(
        "🔧 <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=get_admin_keyboard(),
        parse_mode="HTML"
    )


# @admin_router.callback_query(F.data == "admin_menu")
# async def admin_menu(callback: CallbackQuery):
#     """Возврат в главное меню"""
#     if not check_admin(callback.from_user.id):
#         await callback.answer("⛔ Нет доступа", show_alert=True)
#         return
#     await callback.message.edit_text(
#         "🔧 <b>Админ-панель</b>\n\nВыберите действие:",
#         reply_markup=get_admin_keyboard(),
#         parse_mode="HTML"
#     )
#     await callback.answer()


# @admin_router.callback_query(F.data == "admin_generate_plan")
# async def admin_generate_plan(callback: CallbackQuery):
#     """Генерация контент-плана на неделю"""
#     if not check_admin(callback.from_user.id):
#         await callback.answer("⛔ Нет доступа", show_alert=True)
#         return

#     await callback.message.answer("🗓 Генерация контент-плана на неделю...")

#     try:
#         from agents.content_agent import content_agent
#         plan = await content_agent.generate_week_plan()

#         # Формируем сообщение с планом
#         plan_text = "🗓 <b>Контент-план на неделю</b>\n\n"
#         for day in plan:
#             plan_text += f"📅 {day['date']}\n"
#             plan_text += f"📋 {day['topic']}\n"
#             plan_text += f"📝 {day['text'][:100]}...\n\n"

#         await callback.message.answer(plan_text, parse_mode="HTML")
#         await callback.message.answer("✅ Контент-план сгенерирован успешно!")

#     except Exception as e:
#         logger.error(f"Ошибка при генерации плана: {e}")
#         await callback.message.answer(f"❌ Ошибка при генерации плана: {e}")

#     await callback.answer()


@router.callback_query(F.data == "admin:interview")
async def start_interview(callback: CallbackQuery, state: FSMContext):
    """Начало режима интервью"""
    await callback.message.answer(
        "🎙 <b>Режим Интервью активирован.</b>\n\n"
        "Юлия, запишите голосовое сообщение с вашей мыслью или новостью. "
        "Я расшифрую его, структурирую и подготовлю варианты постов для ТЕРИОН или Дом Гранд.",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.waiting_for_voice)
    await callback.answer()


@router.callback_query(F.data == "admin_run_spy")
async def admin_run_spy(callback: CallbackQuery):
    """Принудительный запуск Discovery и Scout-Parser"""
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

    await callback.answer()


@router.message(AdminStates.waiting_for_voice, F.voice)
async def process_interview_voice(message: Message, state: FSMContext):
    """Обработка вашего голоса"""
    waiting_msg = await message.answer("Wait... 🔄 Расшифровываю вашу мысль и подбираю стиль...")

    # 1. Получаем текст из голоса (через нашу утилиту)
    voice_text = await convert_voice_to_text(message.voice.file_id) # Функция в utils

    # 2. Передаем текст Контент-Агенту для создания поста
    # Антон сам определит канал на основе ключевых слов
    post_variants = await content_agent.create_posts_from_interview(voice_text)

    await waiting_msg.delete()
    await message.answer(
        f"✅ <b>Мысль обработана!</b>\n\n"
        f"<b>Исходный текст:</b>\n<i>{voice_text}</i>\n\n"
        f"<b>Предложение Антона:</b>\n{post_variants['text']}\n\n"
        f"📍 <b>Рекомендованный канал:</b> {post_variants['target_channel']}",
        parse_mode="HTML"
    )
    await state.clear()


def register_handlers(dp: Dispatcher):
    """Регистрация обработчиков админ-панели"""
    dp.include_router(router)
