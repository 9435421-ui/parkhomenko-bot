from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from config import LEADS_GROUP_CHAT_ID as ADMIN_GROUP_ID, THREAD_ID_KVARTIRY, THREAD_ID_KOMMERCIA, THREAD_ID_DOMA, THREAD_ID_LOGS
from database.db import db
from utils.voice_handler import voice_handler
from utils.notifications import notify_admin_new_lead
from services.lead_service import send_lead_to_admin_group, send_contact_to_logs
import json
import re
import os
import tempfile
import logging
from utils.time_utils import is_working_hours
from utils.moderation import contains_bad_words

logger = logging.getLogger(__name__)

router = Router()

class QuizOrder(StatesGroup):
    city = State()
    obj_type = State()
    floor_info = State()
    area = State()
    status = State()
    changes_desc = State()
    has_plan = State()
    plan_file = State()
    extra_info = State()  # Для приема данных после финала

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

            text = await voice_handler.transcribe(dest.name)
            os.unlink(dest.name)

            if text:
                await message.answer(f"🎤 Распознано: «{text}»")
                return text
        except Exception as e:
            logger.error(f"Ошибка транскрибации: {e}")
            return None
    return message.text

async def handle_initial_contact(message: Message, state: FSMContext):
    """Первичное сохранение лида и уведомление админа"""
    phone = message.contact.phone_number
    name = message.from_user.full_name
    username = message.from_user.username
    user_id = message.from_user.id

    await state.update_data(
        phone=phone,
        name=name,
        username=username
    )

    # Сохраняем первичный лид в БД
    lead_id = await db.upsert_unified_lead(
        user_id=user_id,
        source_bot="qualification",
        phone=phone,
        name=name,
        lead_type="initial_contact",
        details=json.dumps({"username": username}, ensure_ascii=False)
    )

    # Также обновляем телефон в таблице пользователей
    await db.update_user(user_id, phone=phone)

    # Уведомляем админа (в группу через сервис и в ЛС через утилиту)
    try:
        await send_contact_to_logs(message.bot, {
            'user_id': user_id,
            'name': name,
            'phone': phone
        })

        # Дублируем "карточкой" в ЛС админу
        lead_data = {
            'user_id': user_id,
            'name': name,
            'phone': phone,
            'source_bot': 'qualification',
            'lead_type': 'initial_contact',
            'details': {}
        }
        await notify_admin_new_lead(message.bot, lead_id, lead_data)
    except Exception as e:
        logger.error(f"❌ Ошибка уведомления админа о контакте {user_id}: {e}")

@router.message(QuizOrder.city)
async def ask_city(message: Message, state: FSMContext):
    text = await get_text_from_message(message)
    if not text:
        await message.answer("Пожалуйста, укажите город.")
        return

    await state.update_data(city=text)
    await state.set_state(QuizOrder.obj_type)

    markup = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Квартира"), KeyboardButton(text="Коммерция")],
            [KeyboardButton(text="Дом")]
        ],
        resize_keyboard=True
    )
    await message.answer("2. Тип объекта:", reply_markup=markup)

@router.message(QuizOrder.obj_type)
async def ask_obj_type(message: Message, state: FSMContext):
    text = await get_text_from_message(message)
    if text not in ["Квартира", "Коммерция", "Дом"]:
        await message.answer("Пожалуйста, выберите тип объекта из списка.")
        return

    await state.update_data(obj_type=text)
    await state.set_state(QuizOrder.floor_info)
    await message.answer("3. Этаж и общая этажность дома:", reply_markup=ReplyKeyboardRemove())

@router.message(QuizOrder.floor_info)
async def ask_floor(message: Message, state: FSMContext):
    text = await get_text_from_message(message)
    await state.update_data(floor_info=text)
    await state.set_state(QuizOrder.area)
    await message.answer("4. Площадь объекта (кв/м):")

@router.message(QuizOrder.area)
async def ask_area(message: Message, state: FSMContext):
    text = await get_text_from_message(message)
    await state.update_data(area=text)
    await state.set_state(QuizOrder.status)

    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Планируется"), KeyboardButton(text="Уже выполнена")]],
        resize_keyboard=True
    )
    await message.answer("5. Статус: Планируется или уже выполнена перепланировка?", reply_markup=markup)

@router.message(QuizOrder.status)
async def ask_status(message: Message, state: FSMContext):
    text = await get_text_from_message(message)
    if text not in ["Планируется", "Уже выполнена"]:
        await message.answer("Пожалуйста, выберите статус из списка.")
        return

    await state.update_data(status=text)
    await state.set_state(QuizOrder.changes_desc)
    await message.answer("6. Описание изменений: Какие правки хотите сделать или уже сделали?", reply_markup=ReplyKeyboardRemove())

@router.message(QuizOrder.changes_desc)
async def ask_changes_desc(message: Message, state: FSMContext):
    text = await get_text_from_message(message)
    await state.update_data(changes_desc=text)
    await state.set_state(QuizOrder.has_plan)

    markup = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]],
        resize_keyboard=True
    )
    await message.answer("7. У вас есть план помещения?", reply_markup=markup)

@router.message(QuizOrder.has_plan)
async def ask_has_plan(message: Message, state: FSMContext):
    text = await get_text_from_message(message)
    if text == "Да":
        await state.update_data(has_plan=True)
        await state.set_state(QuizOrder.plan_file)
        await message.answer("Пожалуйста, загрузите файл (фото/PDF):", reply_markup=ReplyKeyboardRemove())
    elif text == "Нет":
        await state.update_data(has_plan=False)
        await finalize_quiz(message, state)
    else:
        await message.answer("Пожалуйста, выберите Да или Нет.")

@router.message(QuizOrder.plan_file)
async def handle_plan_file(message: Message, state: FSMContext):
    if message.document:
        await state.update_data(plan_file_id=message.document.file_id)
        await state.update_data(plan_file_type="PDF/Doc")
    elif message.photo:
        await state.update_data(plan_file_id=message.photo[-1].file_id)
        await state.update_data(plan_file_type="Photo")
    else:
        await message.answer("Пожалуйста, пришлите файл или фото плана.")
        return

    await finalize_quiz(message, state)

async def finalize_quiz(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id

    # Подготавливаем данные для сервиса
    lead_data = data.copy()
    lead_data['user_id'] = user_id
    lead_data['name'] = message.from_user.full_name
    lead_data['username'] = message.from_user.username

    # Сохранение в БД
    lead_id = await db.upsert_unified_lead(
        user_id=user_id,
        source_bot="qualification",
        phone=data.get('phone'),
        name=message.from_user.full_name,
        lead_type="quiz_v2_completed",
        details=json.dumps(data, ensure_ascii=False)
    )

    try:
        # Уведомление в группу через сервис
        await send_lead_to_admin_group(message.bot, lead_data)

        # Уведомление в ЛС админу карточкой
        lead_msg_data = {
            'user_id': user_id,
            'name': message.from_user.full_name,
            'phone': data.get('phone'),
            'source_bot': 'qualification',
            'lead_type': 'quiz_completed',
            'details': data
        }
        await notify_admin_new_lead(message.bot, lead_id, lead_msg_data)
    except Exception as e:
        logger.error(f"Ошибка уведомления админа: {e}")

    # Финальное сообщение пользователю
    final_text = "Я передал информацию нашему эксперту, он свяжется с вами в ближайшее время."
    if not is_working_hours():
        final_text += "\nНаш специалист свяжется с вами в ближайшее рабочее время."

    await message.answer(final_text, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())

    await message.answer(
        "Если у вас остались вопросы или вы хотите приложить доп. документы, "
        "отправьте их в этом чате, также вы можете оставить голосовое сообщение (я его распознаю).",
        parse_mode="HTML"
    )
    
    # Переводим в состояние приема доп. данных
    await state.set_state(QuizOrder.extra_info)

@router.message(QuizOrder.extra_info)
async def handle_extra_info(message: Message, state: FSMContext):
    """Обработка доп. документов и вопросов после финала"""
    user_id = message.from_user.id

    # Если голосовое - транскрибируем
    text = await get_text_from_message(message)

    # Пересылаем админу
    info_text = f"➕ <b>ДОП. ИНФОРМАЦИЯ ОТ КЛИЕНТА</b>\n\n👤 {message.from_user.full_name}\n🆔 <code>{user_id}</code>\n\n"
    if text:
        info_text += f"💬 {text}"

    # Тред для доп. инфо (используем тот же, что и для квиза, если есть в data, иначе в LOGS)
    data = await state.get_data()
    obj_type = data.get('obj_type', '').lower()
    if 'квартира' in obj_type:
        thread_id = THREAD_ID_KVARTIRY
    elif 'коммерция' in obj_type:
        thread_id = THREAD_ID_KOMMERCIA
    elif 'дом' in obj_type:
        thread_id = THREAD_ID_DOMA
    else:
        thread_id = THREAD_ID_LOGS

    try:
        if message.photo:
            await message.bot.send_photo(ADMIN_GROUP_ID, message.photo[-1].file_id, caption=info_text, parse_mode="HTML", message_thread_id=thread_id)
        elif message.document:
            await message.bot.send_document(ADMIN_GROUP_ID, message.document.file_id, caption=info_text, parse_mode="HTML", message_thread_id=thread_id)
        elif message.voice or message.text:
            await message.bot.send_message(ADMIN_GROUP_ID, info_text, parse_mode="HTML", message_thread_id=thread_id)

        await message.answer("Информация передана эксперту. Спасибо!")
    except Exception as e:
        logger.error(f"Ошибка пересылки доп. инфо: {e}")
