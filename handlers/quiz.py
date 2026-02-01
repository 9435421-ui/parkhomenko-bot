from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from config import ADMIN_GROUP_ID
from database.db import db
from utils.voice_handler import voice_handler
import json
import re
import os
import tempfile

def get_progress_bar(step, total=10):
    return f"📊 Шаг {step} из {total}\n" + "—" * 20 + "\n"

router = Router()

def validate_phone(phone: str) -> bool:
    """Простая валидация номера телефона"""
    clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
    return bool(re.match(r'^(\+7|8|7)\d{10}$', clean_phone))


@router.callback_query(F.data == "mode:quiz")
async def start_quiz_callback(callback: CallbackQuery, state: FSMContext):
    """Запуск квиза из меню"""
    data = await state.get_data()
    # Проверяем согласие и наличие контакта
    if not data.get('consent'):
        from keyboards.main_menu import get_consent_keyboard
        await callback.message.answer(
            "Для начала квиза необходимо подтвердить согласие на обработку данных.",
            reply_markup=get_consent_keyboard()
        )
        await callback.answer()
        return

    if not data.get('phone'):
        from keyboards.main_menu import get_contact_keyboard
        await callback.message.answer(
            "Для начала квиза, пожалуйста, поделитесь вашим контактом.",
            reply_markup=get_contact_keyboard()
        )
        await callback.answer()
        return

    await state.set_state(QuizOrder.role)
    await callback.message.answer("📋 Кто вы? (Собственник/Дизайнер/Застройщик/Инвестор/Другое)")
    await callback.answer()


async def handle_initial_contact(message: Message, state: FSMContext):
    """Первичное сохранение лида и уведомление админа"""
    phone = message.contact.phone_number
    name = message.from_user.full_name
    username = message.from_user.username
    user_id = message.from_user.id

    data = await state.get_data()
    source = data.get('_payload') or 'direct'

    await state.update_data(
        phone=phone,
        name=name,
        username=username
    )

    # Сохраняем в БД
    try:
        await db.upsert_unified_lead(
            user_id=user_id,
            source_bot="qualification",
            phone=phone,
            name=name,
            username=username,
            lead_type="initial_contact",
            consent=1,
            consent_date=data.get('consent_date')
        )
        print(f"✅ Initial lead saved for {user_id}")
    except Exception as e:
        print(f"ERROR lead_save_failed: {e}")
        await message.answer("Произошла ошибка при сохранении вашей заявки, но вы можете продолжить квиз.")

    # Уведомляем админа
    summary = (
        f"📱 <b>ПОЛУЧЕН КОНТАКТ</b>\n\n"
        f"👤 <b>Имя:</b> {name}\n"
        f"📱 <b>Телефон:</b> <code>{phone}</code>\n"
        f"🔗 <b>Источник:</b> {source}\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>"
    )

    try:
        await message.bot.send_message(chat_id=ADMIN_GROUP_ID, text=summary, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка уведомления админа: {e}")


class QuizOrder(StatesGroup):
    role = State()
    city = State()
    obj_type = State()
    floor = State()
    area = State()
    status = State()
    complexity = State()
    goal = State()


def get_progress(step: int, total: int = 8) -> str:
    return f"📍 Шаг {step} из {total}\n\n"

def handle_quiz_start(user_stage="planned"):
    """Placeholder for automation script"""
    # Внедренная логика ветвления
    if user_stage == "planned":
        print("Ветка: Чек-лист")
    else:
        print("Ветка: Легализация")
    pass


async def get_text_from_message(message: Message):
    """Извлекает текст или транскрибирует голос в Aiogram"""
    if message.voice:
        try:
            file_id = message.voice.file_id
            file = await message.bot.get_file(file_id)
            file_path = file.file_path

            # Скачиваем файл
            dest = tempfile.NamedTemporaryFile(suffix=".oga", delete=False)
            await message.bot.download_file(file_path, dest.name)

            text = voice_handler.transcribe(dest.name)
            os.unlink(dest.name)

            if text:
                await message.answer(f"🎤 Распознано: «{text}»")
                return text
        except Exception as e:
            print(f"Ошибка транскрибации: {e}")
            return None
    return message.text


@router.message(QuizOrder.role)
async def ask_role(message: Message, state: FSMContext):
    text = await get_text_from_message(message)
    if not text:
        await message.answer("Пожалуйста, укажите вашу роль (Собственник/Дизайнер и т.д.)")
        return

    await state.update_data(role=text)
    await state.set_state(QuizOrder.city)
    name = message.from_user.first_name or ""

    await message.answer(f"{get_progress(2)}{name}, из какого вы города? (напишите название)", reply_markup=ReplyKeyboardRemove())


@router.message(QuizOrder.city)
async def ask_city(message: Message, state: FSMContext):
    text = await get_text_from_message(message)
    if not text:
        await message.answer("Пожалуйста, укажите город.")
        return

    await state.update_data(city=text)
    await state.set_state(QuizOrder.obj_type)

    name = message.from_user.first_name or ""
    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🏠 Жилое"), KeyboardButton(text="🏢 Нежилое")]],
        resize_keyboard=True
    )
    await message.answer(f"{get_progress(3)}{name}, какой тип объекта?", reply_markup=markup)


@router.message(QuizOrder.obj_type)
async def ask_obj_type(message: Message, state: FSMContext):
    text = await get_text_from_message(message)
    if not text:
        await message.answer("Пожалуйста, выберите тип объекта.")
        return

    await state.update_data(obj_type=text)
    await state.set_state(QuizOrder.floor)

    name = message.from_user.first_name or ""
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Не первый / не последний")],
            [KeyboardButton(text="Первый"), KeyboardButton(text="Последний")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(f"{get_progress(4)}{name}, укажите этаж и этажность дома (например: 5/17) или выберите вариант:", reply_markup=markup)


@router.message(QuizOrder.floor)
async def ask_floor(message: Message, state: FSMContext):
    text = await get_text_from_message(message)
    if not text:
        await message.answer("Пожалуйста, укажите этаж.")
        return

    await state.update_data(floor=text)
    await state.set_state(QuizOrder.area)

    name = message.from_user.first_name or ""
    await message.answer(f"{get_progress(5)}{name}, укажите примерный метраж помещения (кв. м):", reply_markup=ReplyKeyboardRemove())


@router.message(QuizOrder.area)
async def ask_area(message: Message, state: FSMContext):
    text = await get_text_from_message(message)
    if not text or not re.match(r'^\d+([.,]\d+)?$', text.strip()):
        await message.answer("Пожалуйста, введите метраж числом (например: 45 или 62.5)")
        return

    await state.update_data(area=text.replace(',', '.'))
    await state.set_state(QuizOrder.status)

    name = message.from_user.first_name or ""
    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📋 Планируется"), KeyboardButton(text="✅ Уже выполнена")]],
        resize_keyboard=True
    )
    await message.answer(f"{get_progress(6)}{name}, на какой стадии перепланировка?", reply_markup=markup)


@router.message(QuizOrder.status)
async def ask_status(message: Message, state: FSMContext):
    text = await get_text_from_message(message)
    if not text:
        await message.answer("Пожалуйста, выберите стадию.")
        return

    await state.update_data(status=text)
    await state.set_state(QuizOrder.complexity)

    name = message.from_user.first_name or ""
    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🧱 Стены"), KeyboardButton(text="🚿 Мокрые зоны")],
            [KeyboardButton(text="❌ Нет")]
        ],
        resize_keyboard=True
    )
    await message.answer(f"{get_progress(7)}{name}, что планируете менять?", reply_markup=markup)


@router.message(QuizOrder.complexity)
async def ask_complexity(message: Message, state: FSMContext):
    text = await get_text_from_message(message)
    if not text:
        await message.answer("Пожалуйста, выберите вариант.")
        return

    await state.update_data(complexity=text)
    await state.set_state(QuizOrder.goal)

    name = message.from_user.first_name or ""
    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="💰 Инвест"), KeyboardButton(text="🏠 Для жизни")]],
        resize_keyboard=True
    )
    await message.answer(f"{get_progress(8)}{name}, какова цель перепланировки?", reply_markup=markup)


@router.message(QuizOrder.goal)
async def finish_quiz(message: Message, state: FSMContext):
    text = await get_text_from_message(message)
    if not text:
        await message.answer("Пожалуйста, выберите цель.")
        return

    await state.update_data(goal=text)
    data = await state.get_data()

    # Формируем сводку для админа
    summary = (
        f"🚀 <b>НОВАЯ ЗАЯВКА (КВИЗ {data.get('status')})</b>\n\n"
        f"👤 <b>Клиент:</b> {message.from_user.full_name}\n"
        f"🆔 <b>TG ID:</b> <code>{message.from_user.id}</code>\n"
        f"📱 <b>Телефон:</b> {data.get('phone')}\n"
        f"🏙 <b>Город:</b> {data.get('city')}\n"
        f"🏢 <b>Тип:</b> {data.get('obj_type')}\n"
        f"🏢 <b>Этаж:</b> {data.get('floor')}\n"
        f"📐 <b>Метраж:</b> {data.get('area')} м²\n"
        f"🧱 <b>Сложность:</b> {data.get('complexity')}\n"
        f"🎯 <b>Цель:</b> {data.get('goal')}\n"
        f"🔗 <b>Источник:</b> <code>{data.get('_payload') or 'direct'}</code>"
    )

    # Отправка в админ-группу
    try:
        if data.get('bti_file_id'):
            await message.bot.send_document(
                chat_id=ADMIN_GROUP_ID,
                document=data.get('bti_file_id'),
                caption=summary,
                parse_mode="HTML"
            )
        else:
            await message.bot.send_message(chat_id=ADMIN_GROUP_ID, text=summary, parse_mode="HTML")
    except Exception as e:
        print(f"Ошибка отправки уведомления админу: {e}")
        await message.bot.send_message(chat_id=ADMIN_GROUP_ID, text=summary, parse_mode="HTML")

    # Обновляем лид в БД результатами квиза
    try:
        await db.upsert_unified_lead(
            user_id=message.from_user.id,
            source_bot="qualification",
            phone=data.get('phone'),
            name=message.from_user.full_name,
            username=message.from_user.username,
            lead_type="quiz_completed",
            details=json.dumps(data, ensure_ascii=False)
        )
    except Exception as e:
        print(f"Ошибка обновления лида: {e}")

    # Ветвление финального контента для пользователя
    status = data.get('status', '').lower()
    name = message.from_user.first_name or "клиент"

    if "уже выполнена" in status:
        final_text = (
            f"✅ <b>Спасибо, {name}! Ваша заявка принята.</b>\n\n"
            "Так как перепланировка уже выполнена, мы подготовим для вас план легализации:\n"
            "1️⃣ Проверим допустимость выполненных работ.\n"
            "2️⃣ Оценим риски штрафов и предписаний.\n"
            "3️⃣ Подскажем, как узаконить всё без судов.\n\n"
            "Наш эксперт свяжется с вами в ближайшее рабочее время."
        )
    else:
        final_text = (
            f"✅ <b>Спасибо, {name}! Заявка успешно оформлена.</b>\n\n"
            "Для вашей будущей перепланировки мы подготовим:\n"
            "1️⃣ Расчет стоимости проектирования и согласования.\n"
            "2️⃣ Пошаговый алгоритм действий именно для вашего случая.\n"
            "3️⃣ Список необходимых документов БТИ и ЕГРН.\n\n"
            "Эксперт позвонит вам для уточнения деталей."
        )

    # Кнопка для записи на консультацию
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Выбрать время консультации", url="https://t.me/terion_expert")]
        ]
    )
    
    await message.answer(final_text, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    await message.answer("Вы также можете написать нашему эксперту напрямую в Telegram:", reply_markup=markup)

    await state.clear()
