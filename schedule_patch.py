"""
Патч расписания для handlers/content_bot.py
Запуск: python3 schedule_patch.py
Расположение: /root/PARKHOMENKO_BOT/
"""

PATCH_FILE = "/root/PARKHOMENKO_BOT/handlers/content_bot.py"
OLD_QUEUE_KB = '''    builder.button(text="📤 Во все каналы", callback_data=f"pub_all:{post_id}")
    builder.button(text="🚀 GEORIS", callback_data=f"pub_georis:{post_id}")
    builder.button(text="🏘 ДОМ ГРАНД", callback_data=f"pub_dom_grnd:{post_id}")
    builder.button(text="📱 MAX", callback_data=f"pub_max:{post_id}")
    builder.button(text="🌐 VK", callback_data=f"pub_vk:{post_id}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1, 2, 2, 1)
    return builder.as_markup()'''

NEW_QUEUE_KB = '''    builder.button(text="📤 Во все каналы", callback_data=f"pub_all:{post_id}")
    builder.button(text="🚀 GEORIS", callback_data=f"pub_georis:{post_id}")
    builder.button(text="🏘 ДОМ ГРАНД", callback_data=f"pub_dom_grnd:{post_id}")
    builder.button(text="📱 MAX", callback_data=f"pub_max:{post_id}")
    builder.button(text="🌐 VK", callback_data=f"pub_vk:{post_id}")
    builder.button(text="⏰ Запланировать", callback_data=f"schedule:{post_id}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1, 2, 2, 1, 1)
    return builder.as_markup()'''

# ── 2. FSM и хендлер для планирования — вставляем после save_draft ──────────

OLD_AFTER_DRAFT = '''@content_router.callback_query(F.data.startswith("edit:"))
async def edit_handler(callback: CallbackQuery, state: FSMContext):'''

NEW_SCHEDULE_BLOCK = '''# ── Расписание публикаций ────────────────────────────────────────────────────

class SchedulePostStates(StatesGroup):
    waiting_datetime = State()


@content_router.callback_query(F.data.startswith("schedule:"))
async def schedule_post_start(callback: CallbackQuery, state: FSMContext):
    """Запрашиваем дату и время публикации."""
    post_id = int(callback.data.split(":")[1])
    await state.update_data(schedule_post_id=post_id)

    from datetime import datetime, timedelta
    now = datetime.now()
    # Подсказки: сегодня 12:00, завтра 10:00, послезавтра 12:00
    today_12 = now.replace(hour=12, minute=0, second=0, microsecond=0)
    tomorrow_10 = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    tomorrow_12 = (now + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)

    from aiogram.types import InlineKeyboardMarkup
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Сегодня 12:00 ({today_12.strftime('%d.%m')})",
                   callback_data=f"sched_quick:{post_id}:{today_12.strftime('%Y-%m-%d %H:%M')}")
    builder.button(text=f"Завтра 10:00 ({tomorrow_10.strftime('%d.%m')})",
                   callback_data=f"sched_quick:{post_id}:{tomorrow_10.strftime('%Y-%m-%d %H:%M')}")
    builder.button(text=f"Завтра 12:00 ({tomorrow_12.strftime('%d.%m')})",
                   callback_data=f"sched_quick:{post_id}:{tomorrow_12.strftime('%Y-%m-%d %H:%M')}")
    builder.button(text="✏️ Ввести вручную", callback_data=f"sched_manual:{post_id}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1)

    await callback.message.answer(
        f"⏰ <b>Запланировать пост #{post_id}</b>\n\n"
        f"Выберите время публикации или введите вручную:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@content_router.callback_query(F.data.startswith("sched_quick:"))
async def schedule_quick(callback: CallbackQuery, state: FSMContext):
    """Быстрый выбор времени из кнопок."""
    parts = callback.data.split(":")
    post_id = int(parts[1])
    dt_str = parts[2] + ":" + parts[3]  # "2026-03-18 12:00"

    await _save_schedule(callback, post_id, dt_str)
    await state.clear()


@content_router.callback_query(F.data.startswith("sched_manual:"))
async def schedule_manual_start(callback: CallbackQuery, state: FSMContext):
    """Запрашиваем ручной ввод даты."""
    post_id = int(callback.data.split(":")[1])
    await state.set_state(SchedulePostStates.waiting_datetime)
    await state.update_data(schedule_post_id=post_id)
    await callback.message.answer(
        "✏️ Введите дату и время публикации в формате:\n"
        "<code>ДД.ММ ЧЧ:ММ</code>\n\n"
        "Например: <code>20.03 14:30</code>",
        parse_mode="HTML"
    )
    await callback.answer()


@content_router.message(SchedulePostStates.waiting_datetime)
async def schedule_manual_input(message, state: FSMContext):
    """Получаем дату от пользователя и сохраняем."""
    data = await state.get_data()
    post_id = data.get("schedule_post_id")

    try:
        from datetime import datetime
        dt = datetime.strptime(message.text.strip(), "%d.%m %H:%M")
        dt = dt.replace(year=datetime.now().year)
        dt_str = dt.strftime("%Y-%m-%d %H:%M")
        await _save_schedule(message, post_id, dt_str, is_message=True)
    except ValueError:
        await message.answer(
            "❌ Неверный формат. Попробуй ещё раз:\n"
            "<code>ДД.ММ ЧЧ:ММ</code> — например <code>20.03 14:30</code>",
            parse_mode="HTML"
        )
        return

    await state.clear()


async def _save_schedule(event, post_id: int, dt_str: str, is_message: bool = False):
    """Сохраняет дату публикации и статус approved в БД."""
    try:
        from datetime import datetime
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")

        await db.update_content_post(post_id, status="approved", publish_date=dt)

        text = (
            f"✅ <b>Пост #{post_id} запланирован!</b>\n\n"
            f"📅 Публикация: <b>{dt.strftime('%d.%m.%Y в %H:%M')}</b>\n\n"
            f"Бот опубликует автоматически во все каналы."
        )
=======
OLD_AFTER_DRAFT = '''@content_router.callback_query(F.data.startswith("edit:"))
async def edit_handler(callback: CallbackQuery, state: FSMContext):'''

NEW_SCHEDULE_BLOCK = '''class SchedulePostStates(StatesGroup):
    waiting_datetime = State()

@content_router.callback_query(F.data.startswith("schedule:"))
async def schedule_post_start(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split(":")[1])
    await state.update_data(schedule_post_id=post_id)
    from datetime import datetime, timedelta
    now = datetime.now()
    today_12 = now.replace(hour=12, minute=0, second=0, microsecond=0)
    tomorrow_10 = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    tomorrow_12 = (now + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Сегодня 12:00 ({today_12.strftime('%d.%m')})", callback_data=f"sched_quick:{post_id}:{today_12.strftime('%Y-%m-%d %H:%M')}")
    builder.button(text=f"Завтра 10:00 ({tomorrow_10.strftime('%d.%m')})", callback_data=f"sched_quick:{post_id}:{tomorrow_10.strftime('%Y-%m-%d %H:%M')}")
    builder.button(text=f"Завтра 12:00 ({tomorrow_12.strftime('%d.%m')})", callback_data=f"sched_quick:{post_id}:{tomorrow_12.strftime('%Y-%m-%d %H:%M')}")
    builder.button(text="✏️ Ввести вручную", callback_data=f"sched_manual:{post_id}")
    builder.button(text="❌ Отмена", callback_data="cancel")
    builder.adjust(1)
    await callback.message.answer(f"⏰ <b>Запланировать пост #{post_id}</b>\n\nВыберите время:", reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@content_router.callback_query(F.data.startswith("sched_quick:"))
async def schedule_quick(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    post_id = int(parts[1])
    dt_str = parts[2] + ":" + parts[3]
    await _save_schedule(callback, post_id, dt_str)
    await state.clear()

@content_router.callback_query(F.data.startswith("sched_manual:"))
async def schedule_manual_start(callback: CallbackQuery, state: FSMContext):
    post_id = int(callback.data.split(":")[1])
    await state.set_state(SchedulePostStates.waiting_datetime)
    await state.update_data(schedule_post_id=post_id)
    await callback.message.answer("✏️ Введите дату и время:\n<code>ДД.ММ ЧЧ:ММ</code>\n\nНапример: <code>20.03 14:30</code>", parse_mode="HTML")
    await callback.answer()

@content_router.message(SchedulePostStates.waiting_datetime)
async def schedule_manual_input(message, state: FSMContext):
    data = await state.get_data()
    post_id = data.get("schedule_post_id")
    try:
        from datetime import datetime
        dt = datetime.strptime(message.text.strip(), "%d.%m %H:%M").replace(year=datetime.now().year)
        await _save_schedule(message, post_id, dt.strftime("%Y-%m-%d %H:%M"), is_message=True)
        await state.clear()
    except ValueError:
        await message.answer("❌ Неверный формат. Пример: <code>20.03 14:30</code>", parse_mode="HTML")

async def _save_schedule(event, post_id: int, dt_str: str, is_message: bool = False):
    try:
        from datetime import datetime
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        await db.update_content_post(post_id, status="approved", publish_date=dt)
        text = f"✅ <b>Пост #{post_id} запланирован!</b>\n\n📅 Публикация: <b>{dt.strftime('%d.%m.%Y в %H:%M')}</b>\n\nБот опубликует автоматически."
>>>>>>> 7aef37fb2cbc26b88258a72b504e3333cd17c745
        if is_message:
            await event.answer(text, parse_mode="HTML")
        else:
            await event.message.answer(text, parse_mode="HTML")
            await event.answer()
    except Exception as e:
        err = f"❌ Ошибка сохранения расписания: {e}"
        if is_message:
            await event.answer(err)
        else:
            await event.answer(err)

@content_router.callback_query(F.data.startswith("edit:"))
async def edit_handler(callback: CallbackQuery, state: FSMContext):'''

def apply_patch():
    with open(PATCH_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # Проверяем что патч ещё не применён
    if "schedule:" in content and "SchedulePostStates" in content:
        print("⚠️  Патч уже применён ранее!")
        return

    # Применяем патч 1: кнопка в клавиатуре
    if OLD_QUEUE_KB not in content:
        print("❌ Не найден блок get_queue_keyboard — проверь вручную")
        return
    content = content.replace(OLD_QUEUE_KB, NEW_QUEUE_KB, 1)
    print("✅ Патч 1: кнопка ⏰ Запланировать добавлена")

    # Применяем патч 2: FSM + хендлеры
    if OLD_AFTER_DRAFT not in content:
        print("❌ Не найден блок edit_handler — проверь вручную")
        return
    content = content.replace(OLD_AFTER_DRAFT, NEW_SCHEDULE_BLOCK, 1)
    print("✅ Патч 2: FSM и хендлеры расписания добавлены")

    # Проверяем что StatesGroup импортирован
    if "StatesGroup" not in content:
=======
    if "SchedulePostStates" in content:
        print("Патч уже применён!")
        return
    if OLD_QUEUE_KB not in content:
        print("ОШИБКА: не найден блок get_queue_keyboard")
        return
    content = content.replace(OLD_QUEUE_KB, NEW_QUEUE_KB, 1)
    print("OK 1: кнопка добавлена")
    if OLD_AFTER_DRAFT not in content:
        print("ОШИБКА: не найден блок edit_handler")
        return
    content = content.replace(OLD_AFTER_DRAFT, NEW_SCHEDULE_BLOCK, 1)
    print("OK 2: FSM добавлен")
    if "from aiogram.fsm.state import State, StatesGroup" not in content:
>>>>>>> 7aef37fb2cbc26b88258a72b504e3333cd17c745
        content = content.replace(
            "from aiogram.fsm.context import FSMContext",
            "from aiogram.fsm.context import FSMContext\nfrom aiogram.fsm.state import State, StatesGroup",
            1
        )
        print("✅ Патч 3: импорт StatesGroup добавлен")

    with open(PATCH_FILE, 'w', encoding='utf-8') as f:
        f.write(content)

    print("\n🎉 Все патчи применены успешно!")
    print("Перезапусти сервис: systemctl restart anton.service")


if __name__ == "__main__":
    apply_patch()
        print("✅ Патч 3: импорт StatesGroup добавлен")

    with open(PATCH_FILE, 'w', encoding='utf-8') as f:
        f.write(content)

    print("\n🎉 Все патчи применены успешно!")
    print("Перезапусти сервис: systemctl restart anton.service")


if __name__ == "__main__":
    apply_patch()
