from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from config import LEADS_GROUP_CHAT_ID, THREAD_ID_KVARTIRY, THREAD_ID_KOMMERCIA, THREAD_ID_DOMA
from keyboards.main_menu import get_object_type_keyboard, get_remodeling_status_keyboard

router = Router()

class QuizOrder(StatesGroup):
    city = State()
    obj_type = State()
    floor_info = State()
    area = State()
    status = State()
    description = State()
    plan_file = State()

@router.message(QuizOrder.city)
async def handle_city(message: Message, state: FSMContext):
    await state.update_data(city=message.text)
    await state.set_state(QuizOrder.obj_type)
    await message.answer("Какой тип объекта? (Жилая/Коммерческая/Инвестиционная)", reply_markup=get_object_type_keyboard())

@router.callback_query(QuizOrder.obj_type, F.data.startswith("obj:"))
async def handle_obj_type(callback: CallbackQuery, state: FSMContext):
    obj_type = "Квартира" if "kvartira" in callback.data else "Коммерция"
    await state.update_data(obj_type=obj_type)
    await state.set_state(QuizOrder.floor_info)
    await callback.message.edit_text("На каком этаже находится объект? Укажите этаж и этажность (например: 5/9):")
    await callback.answer()

@router.message(QuizOrder.floor_info)
async def handle_floor(message: Message, state: FSMContext):
    await state.update_data(floor_info=message.text)
    await state.set_state(QuizOrder.area)
    await message.answer("Какая площадь объекта? (в кв.м.)")

@router.message(QuizOrder.area)
async def handle_area(message: Message, state: FSMContext):
    await state.update_data(area=message.text)
    await state.set_state(QuizOrder.status)
    await message.answer("Какой статус перепланировки? (Планируется/Уже выполнена/В процессе)", reply_markup=get_remodeling_status_keyboard())

@router.callback_query(QuizOrder.status, F.data.startswith("remodel:"))
async def handle_status(callback: CallbackQuery, state: FSMContext):
    status = "Выполнена" if "done" in callback.data else "Планируется"
    await state.update_data(status=status)
    await state.set_state(QuizOrder.description)
    await callback.message.edit_text("Опишите, пожалуйста, что именно вы хотите изменить в планировке?")
    await callback.answer()

@router.message(QuizOrder.description)
async def handle_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(QuizOrder.plan_file)
    await message.answer("Прикрепите, пожалуйста, план помещения или фото (JPG/PDF):")

@router.message(QuizOrder.plan_file, F.photo | F.document)
async def handle_plan_file(message: Message, state: FSMContext):
    data = await state.get_data()
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    thread_id = THREAD_ID_KVARTIRY if data.get('obj_type') == 'Квартира' else THREAD_ID_KOMMERCIA

    summary = (
        f"📋 <b>Новая заявка</b>\n\n"
        f"🏙 Город: {data.get('city')}\n"
        f"🏗 Тип: {data.get('obj_type')}\n"
        f"🪜 Этаж: {data.get('floor_info')}\n"
        f"📏 Площадь: {data.get('area')}\n"
        f"📅 Статус: {data.get('status')}\n"
        f"📝 Описание: {data.get('description')}\n"
        f"👤 Клиент: @{message.from_user.username or message.from_user.id}"
    )

    await message.bot.send_message(LEADS_GROUP_CHAT_ID, summary, message_thread_id=thread_id, parse_mode="HTML")
    await message.bot.send_document(LEADS_GROUP_CHAT_ID, file_id, message_thread_id=thread_id)
    await message.answer("Спасибо! Юлия Пархоменко свяжется с вами для анализа.", reply_markup=ReplyKeyboardRemove())
    await state.clear()
