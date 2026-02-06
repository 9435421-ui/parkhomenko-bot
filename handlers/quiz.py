from aiogram import Router, F
from aiogram.types import Message, ContentType
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from config import LEADS_GROUP_CHAT_ID

router = Router()


class QuizOrder(StatesGroup):
    city = State()
    obj_type = State()
    floor = State()
    area = State()
    status = State()
    description = State()
    plan = State()
    phone = State()


@router.message(QuizOrder.city)
async def ask_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(QuizOrder.obj_type)
    await message.answer("Какой тип объекта? (Жилая/Коммерческая/Инвестиционная)")


@router.message(QuizOrder.obj_type)
async def ask_obj_type(message: Message, state: FSMContext):
    await state.update_data(obj_type=message.text)
    await state.set_state(QuizOrder.floor)
    await message.answer("На каком этаже находится объект? (1-й/2-й/3-й/4-й/5-й/6-й/7-й/8-й/9-й/10-й/11-й/12-й/13-й/14-й/15-й/16-й/17-й/18-й/19-й/20-й/21-й/22-й/23-й/24-й/25-й/26-й/27-й/28-й/29-й/30-й/31-й/32-й/33-й/34-й/35-й/36-й/37-й/38-й/39-й/40-й/41-й/42-й/43-й/44-й/45-й/46-й/47-й/48-й/49-й/50-й/51-й/52-й/53-й/54-й/55-й/56-й/57-й/58-й/59-й/60-й/61-й/62-й/63-й/64-й/65-й/66-й/67-й/68-й/69-й/70-й/71-й/72-й/73-й/74-й/75-й/76-й/77-й/78-й/79-й/80-й/81-й/82-й/83-й/84-й/85-й/86-й/87-й/88-й/89-й/90-й/91-й/92-й/93-й/94-й/95-й/96-й/97-й/98-й/99-й/100-й)")


@router.message(QuizOrder.floor)
async def ask_floor(message: Message, state: FSMContext):
    await state.update_data(floor=message.text)
    await state.set_state(QuizOrder.area)
    await message.answer("Какая площадь объекта? (в кв.м.)")


@router.message(QuizOrder.area)
async def ask_area(message: Message, state: FSMContext):
    await state.update_data(area=message.text)
    await state.set_state(QuizOrder.status)
    await message.answer("Какой статус перепланировки? (Планируется/Уже выполнена/В процессе)")


@router.message(QuizOrder.status)
async def ask_status(message: Message, state: FSMContext):
    await state.update_data(status=message.text)
    await state.set_state(QuizOrder.description)
    await message.answer("Опишите, пожалуйста, что именно вы хотите изменить в планировке?")


@router.message(QuizOrder.description)
async def ask_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(QuizOrder.plan)
    await message.answer("Есть ли у вас готовый проект перепланировки? (Да/Нет)")


@router.message(QuizOrder.plan)
async def ask_plan(message: Message, state: FSMContext):
    await state.update_data(plan=message.text)
    await state.set_state(QuizOrder.phone)
    await message.answer("Оставьте, пожалуйста, ваш номер телефона для связи.")


@router.message(QuizOrder.phone)
async def finish_quiz(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    data = await state.get_data()

    # Определение thread_id в зависимости от типа объекта
    thread_id = 2 if data.get('obj_type') == 'Жилая' else 5

    summary = (
        f"📋 Новая заявка от пользователя @{message.from_user.username or message.from_user.id}:\n\n"
        f"🏙 Город: {data.get('city')}\n"
        f"🏗 Тип объекта: {data.get('obj_type')}\n"
        f"🪜 Этаж: {data.get('floor')}\n"
        f"📏 Площадь: {data.get('area')} кв.м.\n"
        f"📅 Статус: {data.get('status')}\n"
        f"📝 Описание: {data.get('description')}\n"
        f"📄 Проект: {data.get('plan')}\n"
        f"📞 Телефон: {data.get('phone')}"
    )

    # Отправка отчета в указанный чат с thread_id
    await message.bot.send_message(
        chat_id=LEADS_GROUP_CHAT_ID,
        text=summary,
        thread_id=thread_id
    )

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
    await message.answer("Спасибо! Эксперт команды Терион свяжется с вами для дальнейшего анализа.")
    await state.clear()


@router.message(F.photo | F.document)
async def handle_media(message: Message, state: FSMContext):
    """Обработка фото/файлов в последнем вопросе"""
    if state.current_state() == QuizOrder.plan:
        await message.answer("Спасибо за предоставленные документы! Теперь оставьте, пожалуйста, ваш номер телефона для связи.")
        await state.set_state(QuizOrder.phone)
    else:
        await message.answer("Пожалуйста, ответьте на текущий вопрос.")