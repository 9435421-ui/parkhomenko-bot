from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from config import ADMIN_GROUP_ID

router = Router()


class QuizOrder(StatesGroup):
    phone = State()
    city = State()
    obj_type = State()
    status = State()
    complexity = State()
    goal = State()
    bti_doc = State()
    urgency = State()


@router.message(QuizOrder.phone)
async def handle_phone(message: Message, state: FSMContext):
    # Мгновенное сохранение лида
    from utils.time_utils import is_working_hours
    from database.db import db
    from services.lead_service import lead_service

    phone = message.text.strip()
    await state.update_data(phone=phone)

    is_night = not is_working_hours()
    user_id = message.from_user.id

    # Сохраняем в БД
    await db.save_lead(
        user_id,
        name=message.from_user.first_name,
        phone=phone,
        qualification_started=True,
        night_lead=is_night
    )

    # Уведомление в группу
    await lead_service.send_qualification_notification(message.bot, phone, is_night)

    data = await state.get_data()
    payload = data.get('_payload', '')

    # Все пути в этом квизе ведут к вопросу о городе
    await state.set_state(QuizOrder.city)

    if payload == 'invest':
        await message.answer("✅ Контакт сохранен. 💰 Давайте оценим капитализацию вашего объекта. В каком городе он находится?")
    elif payload == 'expert':
        await message.answer("✅ Контакт сохранен. 🔍 Начнем экспертную оценку. В каком городе находится объект?")
    elif payload == 'price':
        await message.answer("✅ Контакт сохранен. 🧮 Рассчитаем стоимость. В каком городе находится объект?")
    elif payload == 'quiz':
        await message.answer("✅ Контакт сохранен. 📋 Для начала, в каком городе находится объект?")
    else:
        await message.answer("✅ Контакт сохранен. Для подготовки предложения, в каком городе находится объект?")


@router.message(QuizOrder.city)
async def ask_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(QuizOrder.obj_type)
    await message.answer("Какой тип объекта? (Жилое/Нежилое)")


@router.message(QuizOrder.obj_type)
async def ask_obj_type(message: Message, state: FSMContext):
    await state.update_data(obj_type=message.text)
    await state.set_state(QuizOrder.status)
    await message.answer("На какой стадии перепланировка? (Планируется/Уже выполнена)")


@router.message(QuizOrder.status)
async def ask_status(message: Message, state: FSMContext):
    await state.update_data(status=message.text)
    await state.set_state(QuizOrder.complexity)
    await message.answer("Есть ли сложные зоны? (Стены/Мокрые зоны/Нет)")


@router.message(QuizOrder.complexity)
async def ask_complexity(message: Message, state: FSMContext):
    await state.update_data(complexity=message.text)
    await state.set_state(QuizOrder.goal)
    await message.answer("Какова цель перепланировки? (Инвест/Для жизни)")


@router.message(QuizOrder.goal)
async def ask_goal(message: Message, state: FSMContext):
    await state.update_data(goal=message.text)
    await state.set_state(QuizOrder.bti_doc)
    await message.answer("Есть ли документы БТИ? (Да/Частично/Нет)")


@router.message(QuizOrder.bti_doc)
async def ask_bti(message: Message, state: FSMContext):
    await state.update_data(bti_doc=message.text)
    await state.set_state(QuizOrder.urgency)
    await message.answer("Насколько срочно нужно решить вопрос? (Срочно/Можно подождать)")


@router.message(QuizOrder.urgency)
async def finish_quiz(message: Message, state: FSMContext):
    await state.update_data(urgency=message.text)
    data = await state.get_data()

    # Дополняем лид в БД
    from database.db import db
    await db.save_lead(
        message.from_user.id,
        city=data.get('city'),
        object_type=data.get('obj_type'),
        remodeling_status=data.get('status'),
        change_plan=f"Сложность: {data.get('complexity')}, Цель: {data.get('goal')}",
        bti_status=data.get('bti_doc')
    )

    summary = (
        f"📋 Новая заявка от пользователя @{message.from_user.username or message.from_user.id}:\n\n"
        f"🏙 Город: {data.get('city')}\n"
        f"🏗 Тип объекта: {data.get('obj_type')}\n"
        f"📅 Стадия: {data.get('status')}\n"
        f"🧱 Сложность: {data.get('complexity')}\n"
        f"🎯 Цель: {data.get('goal')}\n"
        f"📄 БТИ: {data.get('bti_doc')}\n"
        f"⏱ Срочность: {data.get('urgency')}\n"
        f"📞 Телефон: {data.get('phone')}"
    )

    await message.bot.send_message(chat_id=ADMIN_GROUP_ID, text=summary)
    
    # Выдача чек-листа
    checklist = (
        "📋 <b>Чек-лист документов для перепланировки:</b>\n\n"
        "1. <b>ЕГРН</b> - выписка из реестра прав собственности\n"
        "2. <b>БТИ</b> - технический паспорт и поэтажный план\n"
        "3. <b>Согласие</b> - документы от всех собственников\n"
        "4. Проект перепланировки (если требуется)\n\n"
        "<i>Правильно оформленные документы упрощают пользование имуществом.</i>"
    )
    
    await message.answer(checklist, parse_mode="HTML")
    await message.answer("Спасибо! Наш эксперт свяжется с вами для анализа.")
    await state.clear()
