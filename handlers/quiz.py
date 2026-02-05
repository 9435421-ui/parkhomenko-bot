from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from config import ADMIN_GROUP_ID
from keyboards.main_menu import get_object_type_keyboard, get_remodeling_status_keyboard

router = Router()


class QuizOrder(StatesGroup):
    city = State()
    obj_type = State()
    floor = State()
    area = State()
    status = State()
    description = State()
    layout_file = State()


@router.message(QuizOrder.city)
async def ask_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(QuizOrder.obj_type)
    await message.answer("🏗 Какой тип объекта?", reply_markup=get_object_type_keyboard())


@router.callback_query(QuizOrder.obj_type, F.data.startswith("obj:"))
async def handle_obj_type(callback: CallbackQuery, state: FSMContext):
    obj_type = callback.data.split(":")[1]
    readable_type = {"kvartira": "Квартира", "kommercia": "Коммерция", "dom": "Дом"}.get(obj_type, obj_type)
    await state.update_data(obj_type=readable_type)
    await state.set_state(QuizOrder.floor)
    await callback.message.answer("🏢 На каком этаже находится объект? (И общее количество этажей, например: 5/12)")
    await callback.answer()


@router.message(QuizOrder.floor)
async def ask_floor(message: Message, state: FSMContext):
    await state.update_data(floor=message.text)
    await state.set_state(QuizOrder.area)
    await message.answer("📏 Укажите примерную площадь объекта (в кв. м):")


@router.message(QuizOrder.area)
async def ask_area(message: Message, state: FSMContext):
    await state.update_data(area=message.text)
    await state.set_state(QuizOrder.status)
    await message.answer("📅 На какой стадии перепланировка?", reply_markup=get_remodeling_status_keyboard())


@router.callback_query(QuizOrder.status, F.data.startswith("remodel:"))
async def handle_status(callback: CallbackQuery, state: FSMContext):
    status = callback.data.split(":")[1]
    readable_status = {"done": "Уже выполнена", "planned": "Только планируется"}.get(status, status)
    await state.update_data(status=readable_status)
    await state.set_state(QuizOrder.description)
    await callback.message.answer("🧱 Опишите вкратце планируемые или выполненные изменения:")
    await callback.answer()


@router.message(QuizOrder.description)
async def ask_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(QuizOrder.layout_file)
    await message.answer("📁 Загрузите план помещения или фото БТИ (если есть). Если нет — просто напишите 'нет'.")


@router.message(QuizOrder.layout_file)
async def handle_layout_file(message: Message, state: FSMContext):
    if message.document:
        await state.update_data(layout_file=f"Документ: {message.document.file_name}")
    elif message.photo:
        await state.update_data(layout_file="Фотография")
    else:
        await state.update_data(layout_file=message.text)

    data = await state.get_data()

    summary = (
        f"📋 <b>Новая заявка на перепланировку</b>\n\n"
        f"👤 Пользователь: @{message.from_user.username or 'ID ' + str(message.from_user.id)}\n"
        f"🏙 Город: {data.get('city')}\n"
        f"🏗 Тип: {data.get('obj_type')}\n"
        f"🏢 Этаж: {data.get('floor')}\n"
        f"📏 Площадь: {data.get('area')} м²\n"
        f"📅 Стадия: {data.get('status')}\n"
        f"🧱 Описание: {data.get('description')}\n"
        f"📄 Файл: {data.get('layout_file')}"
    )

    try:
        await message.bot.send_message(chat_id=ADMIN_GROUP_ID, text=summary, parse_mode="HTML")
        await message.answer("✅ Спасибо! Ваша заявка принята. Эксперт Юлия Пархоменко свяжется с вами для детального анализа.")
    except Exception as e:
        print(f"Error sending lead: {e}")
        await message.answer("Произошла ошибка при отправке заявки, но мы её сохранили. Мы свяжемся с вами!")

    await state.clear()
