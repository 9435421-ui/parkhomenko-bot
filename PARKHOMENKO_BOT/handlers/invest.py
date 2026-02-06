"""
Обработчик инвест-калькулятора (оценка капитализации после перепланировки)
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.db import db
from keyboards.main_menu import get_back_to_menu_keyboard

router = Router()


@router.callback_query(F.data == "mode:invest")
async def start_invest_calc(callback: CallbackQuery):
    """Запуск инвест-калькулятора"""
    user_id = callback.from_user.id

    state = await db.get_user_state(user_id)
    name = state.get('name', 'дорогой клиент') if state else 'дорогой клиент'

    await callback.message.edit_text(
        f"💰 <b>Инвест-калькулятор</b>\n\n"
        f"{name}, я помогу оценить потенциальный прирост стоимости вашей квартиры "
        f"после легальной перепланировки.\n\n"
        f"📊 <b>Исследования ТЕРИОН показывают:</b> узаконенная перепланировка увеличивает "
        f"рыночную стоимость объекта на 12-18%.\n\n"
        f"<b>Укажите текущую рыночную стоимость вашей квартиры (в рублях):</b>\n"
        f"Например: 8500000",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(F.text)
async def invest_calc_handler(message: Message):
    """Обработка ввода стоимости и расчёт"""
    user_id = message.from_user.id
    state = await db.get_user_state(user_id)

    # Проверяем, что пользователь в режиме инвест-калькулятора (по логике БД)
    if not state or state.get('mode') != 'invest':
        return

    price_input = message.text.strip()
    name = state.get('name', 'дорогой клиент')

    # Валидация ввода
    try:
        current_price = float(price_input.replace(' ', '').replace(',', '.'))

        if current_price <= 0:
            await message.answer("Пожалуйста, укажите корректную стоимость больше 0")
            return

        if current_price < 100000:
            await message.answer(
                "Кажется, вы указали слишком низкую цену. "
                "Укажите полную рыночную стоимость квартиры в рублях."
            )
            return

    except ValueError:
        return # Игнорируем не-числа, чтобы не мешать другим хендлерам

    # Расчёт капитализации
    min_increase = 0.12
    max_increase = 0.18
    avg_increase = 0.15

    min_new_price = current_price * (1 + min_increase)
    max_new_price = current_price * (1 + max_increase)
    avg_new_price = current_price * (1 + avg_increase)

    min_profit = current_price * min_increase
    max_profit = current_price * max_increase

    def format_rub(value):
        return f"{value:,.0f}".replace(',', ' ')

    await db.update_user_state(user_id, mode=None)

    result_message = f"""
💰 <b>Прогноз капитализации для {name}</b>

📊 <b>Текущая стоимость:</b> {format_rub(current_price)} ₽

📈 <b>Прогнозируемая стоимость после перепланировки:</b>

• <b>Минимальный прогноз (+12%):</b>
  {format_rub(min_new_price)} ₽ (Прирост: <b>+{format_rub(min_profit)} ₽</b>)

• <b>Максимальный прогноз (+18%):</b>
  {format_rub(max_new_price)} ₽ (Прирост: <b>+{format_rub(max_profit)} ₽</b>)

📌 <b>Важно:</b> Это предварительная оценка экспертов ТЕРИОН.
    """.strip()

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Оставить заявку", callback_data="mode:quiz")],
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="back_to_menu")]
        ]
    )

    await message.answer(result_message, parse_mode="HTML", reply_markup=markup)
