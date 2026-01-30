from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from services.content_generator import generator
from database.db import db

router = Router()

class PostCreation(StatesGroup):
    theme = State()
    type = State()
    editing = State()

@router.message(F.text == "📝 Создать пост")
async def start_post_creation(message: Message, state: FSMContext):
    await state.set_state(PostCreation.theme)
    await message.answer("Введите тему поста (например: «Перепланировка кухни в хрущевке»):")

@router.message(PostCreation.theme)
async def process_theme(message: Message, state: FSMContext):
    await state.update_data(theme=message.text)
    await state.set_state(PostCreation.type)
    # Здесь в идеале клавиатура с типами, но пока текстом для MVP
    await message.answer("Выберите тип поста: экспертный, образовательный, продающий, вовлекающий")

@router.message(PostCreation.type)
async def process_type(message: Message, state: FSMContext):
    data = await state.get_data()
    theme = data['theme']
    post_type = message.text

    await message.answer("⌛ Генерирую текст и промпт для изображения...")

    text = await generator.generate_post_text(theme, post_type)
    prompt = await generator.generate_image_prompt(text)

    await state.update_data(text=text, prompt=prompt)
    await state.set_state(PostCreation.editing)

    preview = f"<b>ПРЕВЬЮ ПОСТА:</b>\n\n{text}\n\n<b>ПРОМПТ:</b>\n<i>{prompt}</i>"
    await message.answer(preview, parse_mode="HTML")
    await message.answer("Вы можете отредактировать текст (просто пришлите новый) или подтвердить публикацию.")
