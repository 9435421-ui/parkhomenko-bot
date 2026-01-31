from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from database.db import db
from keyboards.post_keyboards import get_channels_keyboard, get_themes_keyboard, get_skip_keyboard

router = Router()

class PostCreation(StatesGroup):
    selecting_channel = State()
    selecting_theme = State()
    entering_text = State()
    entering_image_desc = State()

@router.message(F.text == "/new_post")
async def start_new_post(message: Message, state: FSMContext):
    channels = await db.get_bots_channels()
    if not channels:
        await message.answer("❌ Каналы не настроены в базе данных.")
        return

    await state.set_state(PostCreation.selecting_channel)
    await message.answer("📢 Выберите канал для публикации:", reply_markup=get_channels_keyboard(channels))

@router.callback_query(PostCreation.selecting_channel, F.data.startswith("channel:"))
async def channel_selected(callback: CallbackQuery, state: FSMContext):
    channel_alias = callback.data.split(":")[1]
    channel_config = await db.get_channel_config(channel_alias)

    await state.update_data(target_channel_alias=channel_alias, brand=channel_config['brand'])
    await state.set_state(PostCreation.selecting_theme)

    await callback.message.edit_text("🎯 Выберите тему поста или введите свою вручную:", reply_markup=get_themes_keyboard())
    await callback.answer()

@router.callback_query(PostCreation.selecting_theme, F.data.startswith("theme:"))
async def theme_selected(callback: CallbackQuery, state: FSMContext):
    theme = callback.data.split(":")[1]
    if theme == "Свой вариант":
        await callback.message.edit_text("✍️ Введите название темы вручную:")
    else:
        await state.update_data(type=theme)
        await state.set_state(PostCreation.entering_text)
        await callback.message.edit_text(f"📝 Тема: {theme}\n\nВведите текст поста:")
    await callback.answer()

@router.message(PostCreation.selecting_theme)
async def manual_theme_entered(message: Message, state: FSMContext):
    await state.update_data(type=message.text)
    await state.set_state(PostCreation.entering_text)
    await message.answer(f"📝 Тема: {message.text}\n\nВведите текст поста:")

@router.message(PostCreation.entering_text)
async def post_text_entered(message: Message, state: FSMContext):
    await state.update_data(body=message.text)
    await state.set_state(PostCreation.entering_image_desc)
    await message.answer("🖼 Введите описание для генерации изображения (или нажмите пропустить):", reply_markup=get_skip_keyboard())

@router.callback_query(PostCreation.entering_image_desc, F.data == "skip")
async def skip_image_desc(callback: CallbackQuery, state: FSMContext):
    await finish_creation(callback.message, state)
    await callback.answer()

@router.message(PostCreation.entering_image_desc)
async def image_desc_entered(message: Message, state: FSMContext):
    await state.update_data(image_description=message.text)
    await finish_creation(message, state)

async def finish_creation(message: Message, state: FSMContext):
    data = await state.get_data()

    # CTA tracking link logic
    brand = data.get('brand')
    cta_start = "torion_main" if brand == "Torion" else "domgrand"
    cta_link = f"https://t.me/torion_bot?start={cta_start}"

    # Validation: mandatory quiz link presence
    body = data.get('body', '')
    if cta_start not in body and cta_link not in body:
        # User didn't include it in text, we will ensure it's at least in cta_link
        # but for strict TZ compliance we might want to warn or auto-append
        body += f"\n\nПереходите по ссылке для расчета: {cta_link}"

    post_id = await db.save_post(
        type=data.get('type'),
        body=body,
        image_description=data.get('image_description'),
        target_channel_alias=data.get('target_channel_alias'),
        brand=brand,
        cta_link=cta_link,
        status='review'
    )

    await db.add_audit_log(
        action="create_post",
        user_id=message.from_user.id if message.from_user else None,
        details=f"Post #{post_id} created for {data.get('target_channel_alias')}"
    )

    await message.answer(f"✅ Пост #{post_id} создан и отправлен на согласование!")

    # In a real scenario, we would notify the review group here
    # For now, we just clear the state
    await state.clear()

    # Trigger review notification (logic will be in review.py)
    from .review import notify_review_group
    await notify_review_group(message.bot, post_id)
