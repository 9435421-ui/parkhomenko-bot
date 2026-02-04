from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from config import ADMIN_GROUP_ID
from datetime import datetime, time
from utils.yandex_gpt import yandex_gpt

quiz_router = Router()


class QuizOrder(StatesGroup):
    city = State()
    obj_type = State()
    floor = State()
    total_floors = State()
    area = State()
    status = State()
    changes = State()
    has_plan = State()
    complexity = State()
    goal = State()
    urgency = State()
    contact = State()
    bti_doc = State()
    legal_doc = State()


@quiz_router.message(QuizOrder.city)
async def ask_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(QuizOrder.obj_type)
    await message.answer("Какой тип объекта? (Квартира / Коммерция)")


@quiz_router.message(QuizOrder.obj_type)
async def ask_obj_type(message: Message, state: FSMContext):
    await state.update_data(obj_type=message.text)
    await state.set_state(QuizOrder.floor)
    await message.answer("Этаж и общая этажность дома? (например: 5/10)")


@quiz_router.message(QuizOrder.floor)
async def ask_floor(message: Message, state: FSMContext):
    await state.update_data(floor=message.text)
    await state.set_state(QuizOrder.area)
    await message.answer("Площадь объекта (кв.м.)?")


@quiz_router.message(QuizOrder.area)
async def ask_area(message: Message, state: FSMContext):
    await state.update_data(area=message.text)
    await state.set_state(QuizOrder.status)
    await message.answer("Статус: Планируется или уже выполнена перепланировка?")


@quiz_router.message(QuizOrder.status)
async def ask_status(message: Message, state: FSMContext):
    await state.update_data(status=message.text)
    await state.set_state(QuizOrder.changes)
    await message.answer("Описание изменений: Что хотите сделать или уже сделали?")


@quiz_router.message(QuizOrder.changes)
async def ask_changes(message: Message, state: FSMContext):
    await state.update_data(changes=message.text)
    await state.set_state(QuizOrder.has_plan)
    await message.answer("Наличие плана: У вас есть план помещения?")


@quiz_router.message(QuizOrder.has_plan)
async def ask_has_plan(message: Message, state: FSMContext):
    await state.update_data(has_plan=message.text)
    if message.text.lower() == "да":
        await state.set_state(QuizOrder.complexity)
        await message.answer("Есть ли сложные зоны? (Стены/Мокрые зоны/Нет)")
    else:
        await state.set_state(QuizOrder.complexity)
        await message.answer("Есть ли сложные зоны? (Стены/Мокрые зоны/Нет)")


@quiz_router.message(QuizOrder.complexity)
async def ask_complexity(message: Message, state: FSMContext):
    await state.update_data(complexity=message.text)
    await state.set_state(QuizOrder.goal)
    await message.answer("Какова цель перепланировки? (Инвест/Для жизни)")


@quiz_router.message(QuizOrder.goal)
async def ask_goal(message: Message, state: FSMContext):
    await state.update_data(goal=message.text)
    await state.set_state(QuizOrder.bti_doc)
    await message.answer("Есть ли документы БТИ? (Да/Частично/Нет)")


@quiz_router.message(QuizOrder.bti_doc)
async def ask_bti(message: Message, state: FSMContext):
    await state.update_data(bti_doc=message.text)
    await state.set_state(QuizOrder.urgency)
    await message.answer("Насколько срочно нужно решить вопрос? (Срочно/Можно подождать)")


@quiz_router.message(QuizOrder.urgency)
async def ask_urgency(message: Message, state: FSMContext):
    await state.update_data(urgency=message.text)
    await state.set_state(QuizOrder.phone)
    await message.answer("Оставьте, пожалуйста, ваш номер телефона для связи.")


@quiz_router.message(QuizOrder.phone)
async def ask_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(QuizOrder.name)
    await message.answer("Как вас зовут?")


@quiz_router.message(QuizOrder.name)
async def ask_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(QuizOrder.email)
    await message.answer("Введите ваш email для связи.")


@quiz_router.message(QuizOrder.email)
async def finish_quiz(message: Message, state: FSMContext):
    await state.update_data(email=message.text)
    data = await state.get_data()

    summary = (
        f"📋 Новая заявка от пользователя @{message.from_user.username or message.from_user.id}:\n\n"
        f"🏙 Город: {data.get('city')}\n"
        f"🏗 Тип объекта: {data.get('obj_type')}\n"
        f"📅 Стадия: {data.get('status')}\n"
        f"🧱 Сложность: {data.get('complexity')}\n"
        f"🎯 Цель: {data.get('goal')}\n"
        f"📄 БТИ: {data.get('bti_doc')}\n"
        f"⏱ Сроность: {data.get('urgency')}\n"
        f"📞 Телефон: {data.get('phone')}\n"
        f"👤 Имя: {data.get('name')}\n"
        f"📧 Email: {data.get('email')}"
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
    await message.answer("Спасибо! Юлия Пархоменко свяжется с вами для анализа.")

    # Режим ожидания
    await message.answer("График работы (МСК): Пн-Пт 9-20, Сб 10-13, Вс вых.")
    if datetime.now().time() > time(20, 0) or datetime.now().time() < time(9, 0):
        await message.answer("Сейчас вне рабочего времени. Юлия Пархоменко свяжется с вами в ближайшее рабочее время.")
    else:
        await message.answer("Юлия Пархоменко свяжется с вами в ближайшее время.")

    await message.answer("Если у вас остались доп. вопросы или документы, вы можете оставить их в этом чате или оставьте голосовое сообщение.")
    await state.clear()


# Обработчик голосовых сообщений
@quiz_router.message(F.voice)
async def handle_voice(message: Message, state: FSMContext):
    # Преобразуем голос в текст
    voice_text = await convert_voice_to_text(message.voice.file_id)
    await message.answer(f"Голосовое сообщение получено:\n\n{voice_text}")
    await message.bot.send_message(chat_id=ADMIN_GROUP_ID, text=f"Голосовое сообщение от @{message.from_user.username}:\n\n{voice_text}")


# Обработчик анти-мата
@quiz_router.message(F.text)
async def handle_text(message: Message, state: FSMContext):
    forbidden_words = ["бля", "хуй", "пизда", "ебать", "сука", "блять", "нахуй", "пидор", "гей", "хуйня"]
    text = message.text.lower()
    if any(word in text for word in forbidden_words):
        await message.answer("Доступ ограничен за нарушение правил общения.")
        await message.bot.kick_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
        await message.bot.send_message(chat_id=ADMIN_GROUP_ID, text=f"Пользователь @{message.from_user.username} заблокирован за нарушение правил.")
        return


async def convert_voice_to_text(file_id: str) -> str:
    """Преобразует голосовое сообщение в текст с помощью Яндекс.ГПТ"""
    yandex_gpt = yandex_gpt
    # Получаем файл голосового сообщения
    file_path = await yandex_gpt.bot.download_file_by_id(file_id)
    # Конвертируем в текст
    voice_text = yandex_gpt.transcribe_audio(file_path)
    return voice_text
