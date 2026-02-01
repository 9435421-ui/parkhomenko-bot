from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from config import ADMIN_GROUP_ID
from database.db import db
import json

router = Router()


@router.callback_query(F.data == "mode:quiz")
async def start_quiz_callback(callback: CallbackQuery, state: FSMContext):
    """Запуск квиза из меню"""
    await state.set_state(QuizOrder.role)
    await callback.message.answer("📋 Кто вы? (Собственник/Дизайнер/Застройщик/Инвестор/Другое)")
    await callback.answer()


class QuizOrder(StatesGroup):
    role = State()
    city = State()
    obj_type = State()
    status = State()
    complexity = State()
    goal = State()
    bti_doc = State()
    urgency = State()
    phone = State()


@router.message(QuizOrder.role)
async def ask_role(message: Message, state: FSMContext):
    await state.update_data(role=message.text)
    await state.set_state(QuizOrder.city)
    await message.answer("Из какого вы города?")


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
async def ask_urgency(message: Message, state: FSMContext):
    await state.update_data(urgency=message.text)
    await state.set_state(QuizOrder.phone)
    await message.answer("Оставьте, пожалуйста, ваш номер телефона для связи.")


@router.message(QuizOrder.phone)
async def finish_quiz(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    data = await state.get_data()

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

    # Сохранение в единую базу лидов
    try:
        await db.add_unified_lead(
            user_id=message.from_user.id,
            source_bot="qualification",
            phone=data.get('phone'),
            name=message.from_user.full_name,
            username=message.from_user.username,
            lead_type="quiz",
            details=json.dumps(data, ensure_ascii=False)
        )
    except Exception as e:
        print(f"Ошибка сохранения лида: {e}")

    await message.answer("Спасибо! Наш эксперт свяжется с вами для анализа.")
    await state.clear()
