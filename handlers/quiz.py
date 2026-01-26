"""
Обработчик 4-шагового квиза ЛАД В КВАРТИРЕ
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import db
from services import lead_service

router = Router()


# Клавиатуры для квиза
def get_city_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора города"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏙️ Москва", callback_data="city:Москва")],
            [InlineKeyboardButton(text="🌆 Московская область", callback_data="city:МО")],
            [InlineKeyboardButton(text="🌉 Санкт-Петербург", callback_data="city:СПб")],
            [InlineKeyboardButton(text="🌍 Другой регион", callback_data="city:other")]
        ]
    )


def get_status_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура статуса перепланировки"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Планирую", callback_data="status:planning")],
            [InlineKeyboardButton(text="🔨 В процессе", callback_data="status:in_progress")],
            [InlineKeyboardButton(text="✅ Сделано", callback_data="status:done")]
        ]
    )


def get_mortgage_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура наличия ипотеки"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да", callback_data="mortgage:yes")],
            [InlineKeyboardButton(text="❌ Нет", callback_data="mortgage:no")]
        ]
    )


# Обработчики callback для квиза
@router.callback_query(F.data == "mode:quiz")
async def start_quiz(callback: CallbackQuery):
    """Запуск квиза"""
    user_id = callback.from_user.id
    
    # Устанавливаем режим квиза и шаг 1
    await db.update_user_state(user_id, mode="quiz", quiz_step=1)
    
    await callback.message.edit_text(
        "📝 <b>Квиз «ЛАД В КВАРТИРЕ»</b>\n\n"
        "Я задам вам 4 коротких вопроса для оформления заявки.\n\n"
        "<b>Вопрос 1 из 4:</b> В каком городе находится объект?",
        reply_markup=get_city_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("city:"))
async def quiz_step_1_city(callback: CallbackQuery):
    """Шаг 1: Выбор города"""
    user_id = callback.from_user.id
    city_code = callback.data.split(":")[1]
    
    city_mapping = {
        "Москва": "Москва",
        "МО": "Московская область",
        "СПб": "Санкт-Петербург",
        "other": "Другой регион"
    }
    
    city = city_mapping.get(city_code, city_code)
    
    # Если другой регион - запрашиваем текстом
    if city == "Другой регион":
        await db.update_user_state(user_id, quiz_step=1, mode="quiz_city_input")
        await callback.message.edit_text(
            "Укажите ваш город:",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    # Сохраняем город и переходим к шагу 2
    await db.update_user_state(user_id, city=city, quiz_step=2)
    
    await callback.message.edit_text(
        f"<b>Вопрос 2 из 4:</b> Напишите этаж/этажность вашей квартиры\n\n"
        f"📍 Город: {city}\n\n"
        f"Например: 3/12 или просто 5",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(F.text)
async def quiz_text_handler(message: Message):
    """Обработка текстовых ответов в квизе"""
    user_id = message.from_user.id
    state = await db.get_user_state(user_id)
    
    if not state or state.get('mode') not in ['quiz', 'quiz_city_input']:
        # Обработка файлов после квиза
        if state and state.get('mode') == 'post_quiz_files':
            await handle_post_quiz_message(message, user_id, state)
        return
    
    # Ввод города текстом
    if state.get('mode') == 'quiz_city_input':
        city = message.text.strip()
        await db.update_user_state(user_id, city=city, quiz_step=2, mode="quiz")
        
        await message.answer(
            f"<b>Вопрос 2 из 4:</b> Напишите этаж/этажность вашей квартиры\n\n"
            f"📍 Город: {city}\n\n"
            f"Например: 3/12 или просто 5",
            parse_mode="HTML"
        )
        return
    
    # Шаг 2: Этажность
    if state.get('quiz_step') == 2:
        floor_info = message.text.strip()
        
        # Разбираем формат этажа
        if '/' in floor_info:
            parts = floor_info.split('/')
            floor = parts[0].strip()
            total_floors = parts[1].strip()
        else:
            floor = floor_info
            total_floors = ""
        
        await db.update_user_state(user_id, floor=floor, total_floors=total_floors, quiz_step=3)
        
        await message.answer(
            f"<b>Вопрос 3 из 4:</b> На каком этапе вы?\n\n"
            f"📍 {state.get('city')}\n"
            f"🏢 Этаж: {floor_info}",
            reply_markup=get_status_keyboard(),
            parse_mode="HTML"
        )
        return


@router.callback_query(F.data.startswith("status:"))
async def quiz_step_3_status(callback: CallbackQuery):
    """Шаг 3: Статус перепланировки"""
    user_id = callback.from_user.id
    status_code = callback.data.split(":")[1]
    
    status_mapping = {
        "planning": "Планирую",
        "in_progress": "В процессе",
        "done": "Сделано"
    }
    
    status = status_mapping.get(status_code, status_code)
    
    # Сохраняем статус
    state = await db.get_user_state(user_id)
    await db.update_user_state(user_id, remodeling_status=status, quiz_step=4)
    
    floor_display = state.get('floor', '')
    if state.get('total_floors'):
        floor_display += f"/{state.get('total_floors')}"
    
    await callback.message.edit_text(
        f"<b>Вопрос 4 из 4:</b> Ваша квартира в ипотеке?\n\n"
        f"📍 {state.get('city')}\n"
        f"🏢 Этаж: {floor_display}\n"
        f"📊 Статус: {status}",
        reply_markup=get_mortgage_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("mortgage:"))
async def quiz_step_4_mortgage(callback: CallbackQuery):
    """Шаг 4: Ипотека - финальный шаг"""
    user_id = callback.from_user.id
    mortgage_code = callback.data.split(":")[1]
    
    mortgage = "Да" if mortgage_code == "yes" else "Нет"
    
    # Сохраняем ипотеку
    await db.update_user_state(user_id, mortgage=mortgage)
    
    # Финализация квиза
    await finalize_quiz(callback.message, user_id)
    await callback.answer()


async def finalize_quiz(message: Message, user_id: int):
    """Финализация квиза и отправка лида"""
    state = await db.get_user_state(user_id)
    
    floor_display = state.get('floor', '')
    if state.get('total_floors'):
        floor_display += f"/{state.get('total_floors')}"
    
    # Формируем данные лида
    lead_data = {
        'name': state.get('name', 'Не указано'),
        'phone': state.get('phone', 'Не указан'),
        'city': state.get('city', 'Не указан'),
        'floor': floor_display,
        'remodeling_status': state.get('remodeling_status', 'Не указан'),
        'mortgage': state.get('mortgage', 'Не указано'),
        'object_type': 'Квартира',  # По умолчанию
        'extra_contact': '',
        'change_plan': '',
        'bti_status': '',
        'total_floors': ''
    }
    
    # Сохраняем лид в БД
    await db.save_lead(
        user_id=user_id,
        name=lead_data['name'],
        phone=lead_data['phone'],
        city=lead_data['city']
    )
    
    # Отправляем в группу через сервис
    bot = message.bot
    await lead_service.send_lead_to_group(bot, lead_data, user_id)
    
    # Переключаем в режим приёма файлов
    await db.update_user_state(user_id, mode="post_quiz_files", quiz_step=0)
    
    # Новое финальное сообщение
    await message.answer(
        f"✅ <b>Ваша заявка принята! {lead_data['name']}, Юлия Владимировна и команда уже получили уведомление.</b>\n\n"
        f"🕒 <b>Наш график работы:</b> ежедневно с 09:00 до 20:00 (по Москве). "
        f"Если вы пишете нам в нерабочее время, мы свяжемся с вами сразу утром.\n\n"
        f"📂 <b>Не теряйте время:</b> Если у вас есть фото плана БТИ, эскизы или вы хотите подробнее "
        f"описать ситуацию — вы можете прямо сейчас прислать файлы, написать текст или отправить "
        f"голосовое сообщение здесь, в чате. Антон всё сохранит и передаст экспертам!",
        parse_mode="HTML"
    )


async def handle_post_quiz_message(message: Message, user_id: int, state: dict):
    """Обработка сообщений после квиза (файлы, текст, голосовые)"""
    name = state.get('name', 'Клиент')
    
    # Сохраняем сообщение в историю
    if message.text:
        await db.add_dialog_message(user_id, role="user", message=f"[После квиза] {message.text}")
        await message.answer(
            f"{name}, ваше сообщение сохранено и будет передано экспертам. "
            f"Можете продолжать присылать дополнительные материалы!"
        )
    
    elif message.photo:
        photo_id = message.photo[-1].file_id
        caption = message.caption or "Фото без описания"
        await db.add_dialog_message(user_id, role="user", message=f"[После квиза] Фото: {caption}")
        await message.answer(
            f"{name}, фото получено и сохранено! Эксперты получат его при обработке вашей заявки."
        )
    
    elif message.document:
        doc_name = message.document.file_name
        await db.add_dialog_message(user_id, role="user", message=f"[После квиза] Документ: {doc_name}")
        await message.answer(
            f"{name}, документ «{doc_name}» сохранён! Спасибо за предоставленные материалы."
        )
    
    elif message.voice:
        duration = message.voice.duration
        await db.add_dialog_message(user_id, role="user", message=f"[После квиза] Голосовое сообщение ({duration} сек)")
        await message.answer(
            f"{name}, голосовое сообщение получено и сохранено!"
        )


# Обработчики для файлов
@router.message(F.photo)
async def handle_photo(message: Message):
    """Обработка фото"""
    user_id = message.from_user.id
    state = await db.get_user_state(user_id)
    
    if state and state.get('mode') == 'post_quiz_files':
        await handle_post_quiz_message(message, user_id, state)


@router.message(F.document)
async def handle_document(message: Message):
    """Обработка документов"""
    user_id = message.from_user.id
    state = await db.get_user_state(user_id)
    
    if state and state.get('mode') == 'post_quiz_files':
        await handle_post_quiz_message(message, user_id, state)


@router.message(F.voice)
async def handle_voice(message: Message):
    """Обработка голосовых сообщений"""
    user_id = message.from_user.id
    state = await db.get_user_state(user_id)
    
    if state and state.get('mode') == 'post_quiz_files':
        await handle_post_quiz_message(message, user_id, state)
