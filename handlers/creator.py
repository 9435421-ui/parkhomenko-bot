"""
Creator Handler — генерация контента с Retry логикой и финансовым трекингом
"""
import asyncio
import logging
from aiogram import Router, F, Bot, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_ID, CHANNEL_ID_TERION, CHANNEL_ID_DOM_GRAD
from database import db

logger = logging.getLogger(__name__)
creator_router = Router()


# === COST CALCULATOR ===
def get_cost(model: str) -> float:
    """Калькулятор стоимости генерации (рубли)"""
    prices = {
        "nano-banana": 2.50,
        "yandex-art": 1.80,
        "gpt-4o-mini": 0.50,
        "Router (Banana)": 2.50,
        "Yandex ART": 1.80
    }
    return prices.get(model, 0)


# === EXPERT SIGNATURE ===
EXPERT_SIGNATURE = "\n\n---\n🤖 ИИ-помощник Антон\n🏡 Эксперт: Юлия Пархоменко"


# === GENERATION WITH FALLBACK ===
async def generate_content(prompt: str, use_yandex_fallback: bool = False):
    """
    Логика генерации с Fallback (Retry)
    
    Returns:
        tuple: (image_data, cost_rub, model_name)
    """
    from services.image_generator import image_generator
    
    if not use_yandex_fallback:
        try:
            # Основной путь: Router API (Nano Banana)
            logger.info("🎨 Генерация через Router API (Nano Banana)...")
            image_data = await image_generator.generate_cover(prompt, style="modern")
            
            if image_data:
                return image_data, get_cost("nano-banana"), "Nano Banana"
            
            # Если вернулось None — пробуем fallback
            raise Exception("Router API вернул None")
            
        except Exception as e:
            logger.error(f"❌ Ошибка Router API: {e}")
            # Сбой: уведомляем и ждем 5 сек
            logger.warning("⚠️ Сбой Router API. Переключаюсь на Яндекс АРТ...")
            await asyncio.sleep(5)
            return await generate_content(prompt, use_yandex_fallback=True)
    else:
        # Резервный путь: Яндекс АРТ
        logger.info("🎨 Генерация через Яндекс АРТ...")
        image_data = await image_generator.generate_cover(prompt, style="modern")
        
        if image_data:
            return image_data, get_cost("yandex-art"), "Yandex ART"
        
        return None, 0, "Failed"


# === CREATOR STATES ===
class CreatorStates(StatesGroup):
    waiting_for_prompt = State()
    generating = State()
    preview = State()


# === KEYBOARDS ===
def get_creator_menu() -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🎨 ИИ-Креативщик", callback_data="creator_generate")
    builder.button(text="📝 Текст", callback_data="creator_text")
    builder.button(text="◀️ Назад", callback_data="back_menu")
    builder.adjust(1, 2)
    return builder.as_markup()


# === HANDLERS ===
@creator_router.callback_query(F.data == "creator_generate")
async def creator_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало генерации — запрос промпта"""
    await callback.message.edit_text(
        "🎨 <b>ИИ-Креативщик</b>\n\n"
        "Введите описание для генерации изображения:\n\n"
        "Примеры:\n"
        "• Современная гостиная с панорамными окнами\n"
        "• Перепланировка студии в сталинке\n"
        "• Минималистичная кухня-студия",
        parse_mode="HTML"
    )
    await state.set_state(CreatorStates.waiting_for_prompt)
    await callback.answer()


@creator_router.message(CreatorStates.waiting_for_prompt)
async def creator_generate(message: types.Message, state: FSMContext):
    """Генерация изображения"""
    prompt = message.text
    
    await message.answer("⏳ <b>Генерирую...</b>", parse_mode="HTML")
    await state.set_state(CreatorStates.generating)
    
    # Генерируем с fallback
    image_data, cost, model = await generate_content(prompt)
    
    if not image_data:
        await message.answer(
            "❌ Не удалось сгенерировать изображение. Попробуйте позже.",
            reply_markup=get_creator_menu()
        )
        await state.clear()
        return
    
    # Сохраняем в историю
    await db.add_content_history(
        post_text=prompt,
        model_used=model,
        cost_rub=cost,
        platform="TG",
        channel="creator"
    )
    
    # Показываем результат
    from aiogram.types import BufferedInputFile
    photo = BufferedInputFile(image_data, filename="generated.jpg")
    
    await message.answer_photo(
        photo=photo,
        caption=(
            f"✅ <b>Готово!</b>\n\n"
            f"🎨 <b>Модель:</b> {model}\n"
            f"💰 <b>Стоимость:</b> {cost}₽"
        ),
        parse_mode="HTML"
    )
    
    # Сохраняем изображение в state для публикации с картинкой
    await state.update_data(image_data=image_data, cost=cost)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Создать пост", callback_data=f"creator_post:{prompt}")
    builder.button(text="🔄 Ещё", callback_data="creator_generate")
    builder.button(text="◀️ Меню", callback_data="back_menu")
    
    await message.answer(
        "Выберите действие:",
        reply_markup=builder.as_markup()
    )


@creator_router.callback_query(F.data.startswith("creator_post:"))
async def creator_make_post(callback: types.CallbackQuery, state: FSMContext):
    """Создание поста из сгенерированного изображения"""
    prompt = callback.data.replace("creator_post:", "")
    
    await callback.message.edit_text(
        "📝 <b>Создание поста</b>\n\n"
        "Введите текст поста:",
        parse_mode="HTML"
    )
    await state.update_data(prompt=prompt, image_generated=True)
    await state.set_state(CreatorStates.preview)
    await callback.answer()


@creator_router.message(CreatorStates.preview)
async def creator_preview(message: types.Message, state: FSMContext):
    """Превью поста с подписью эксперта"""
    data = await state.get_data()
    user_text = message.text
    
    # Добавляем подпись эксперта
    final_text = f"{user_text}{EXPERT_SIGNATURE}"
    
    await message.answer(
        f"👁 <b>Предпросмотр</b>\n\n{final_text[:500]}...",
        parse_mode="HTML"
    )
    
    # Кнопки публикации (TERION, ДОМ ГРАНД, MAX)
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 TERION", callback_data="pub_creator:terion")
    builder.button(text="🏘 ДОМ ГРАНД", callback_data="pub_creator:dom_grnd")
    builder.button(text="📱 MAX", callback_data="pub_creator:max")
    builder.button(text="❌ Отмена", callback_data="cancel")
    
    await message.answer(
        "Выберите канал для публикации:",
        reply_markup=builder.as_markup()
    )
    
    await state.update_data(post_text=user_text, final_text=final_text)


@creator_router.callback_query(F.data.startswith("pub_creator:"))
async def publish_creator_post(callback: types.CallbackQuery, state: FSMContext):
    """Публикация поста в TERION, ДОМ ГРАНД или MAX"""
    channel = callback.data.replace("pub_creator:", "")
    data = await state.get_data()
    final_text = data.get("final_text", data.get("post_text", ""))

    if channel == "max":
        await callback.answer("📱 Публикация в MAX...")
        try:
            from content_agent import ContentAgent
            # Сохраняем пост в БД и публикуем в MAX
            from database import db
            post_id = await db.add_content_post(
                title="Creator",
                body=final_text,
                cta="",
                channel="creator",
                status="draft",
            )
            agent = ContentAgent()
            ok = await agent.post_to_max(post_id)
            if ok:
                await db.update_content_post(post_id, status="published")
                await callback.message.edit_text(
                    "✅ Пост опубликован в MAX",
                    reply_markup=get_creator_menu()
                )
            else:
                await callback.message.edit_text(
                    "❌ Ошибка публикации в MAX. Проверьте MAX_DEVICE_TOKEN.",
                    reply_markup=get_creator_menu()
                )
        except Exception as e:
            logger.exception("pub_creator max")
            await callback.message.edit_text(
                f"❌ Ошибка MAX: {e}",
                reply_markup=get_creator_menu()
            )
        await state.clear()
        return

    if channel == "terion":
        channel_id = CHANNEL_ID_TERION
    else:
        channel_id = CHANNEL_ID_DOM_GRAD

    await callback.answer(f"🚀 Публикую в {channel.upper()}...")
    try:
        from aiogram.types import BufferedInputFile
        image_data = data.get("image_data")
        if image_data:
            photo = BufferedInputFile(image_data, filename="post.jpg")
            await callback.bot.send_photo(channel_id, photo=photo, caption=final_text[:1024], parse_mode="HTML")
        else:
            await callback.bot.send_message(channel_id, final_text, parse_mode="HTML")
        await callback.message.edit_text(
            f"✅ Пост опубликован в {channel.upper()}",
            reply_markup=get_creator_menu()
        )
    except Exception as e:
        logger.exception("pub_creator")
        await callback.message.edit_text(
            f"❌ Ошибка: {e}",
            reply_markup=get_creator_menu()
        )
    cost = data.get("cost", 0)
    await callback.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"💰 Пост в {channel.upper()} опубликован. Списано: {cost}₽"
    )
    await state.clear()


@creator_router.callback_query(F.data == "cancel")
async def creator_cancel(callback: types.CallbackQuery, state: FSMContext):
    """Отмена — назад в меню создателя"""
    await state.clear()
    await callback.message.edit_text(
        "❌ Отменено.\n\nВыберите действие:",
        reply_markup=get_creator_menu()
    )
    await callback.answer()


# === MAIN MENU ENTRY (Создать пост → Текст/Фото/ИИ-Визуал) ===
@creator_router.callback_query(F.data.in_(["content_visual", "content_text", "content_photo"]))
async def content_menu_handler(callback: types.CallbackQuery, state: FSMContext):
    """Текст / Фото / ИИ-Визуал из главного меню"""
    await state.clear()
    if callback.data == "content_visual":
        await creator_start(callback, state)
        return
    if callback.data == "content_text":
        await callback.message.edit_text(
            "📝 <b>Текст</b>\n\nВведите текст поста:",
            parse_mode="HTML"
        )
        await state.set_state(CreatorStates.preview)
        await state.update_data(post_text="", image_data=None, image_generated=False)
    else:
        # content_photo: пока тот же поток (текст). Полноценно «фото + подпись» — в контент-боте
        await callback.message.edit_text(
            "📝 <b>Текст поста</b>\n\nВведите текст (посты с фото удобнее в контент-боте: 📸 Фото → Описание → Пост):",
            parse_mode="HTML"
        )
        await state.set_state(CreatorStates.preview)
        await state.update_data(post_text="", image_data=None, image_generated=False)
    await callback.answer()


async def show_creator_menu(message: types.Message):
    """Показать меню создателя контента"""
    await message.answer(
        "🎨 <b>ИИ-Креативщик</b>\n\n"
        "Создание контента с ИИ:\n"
        "• Генерация изображений\n"
        "• Написание постов\n"
        "• Публикация в каналы (TERION / ДОМ ГРАНД / MAX)",
        reply_markup=get_creator_menu(),
        parse_mode="HTML"
    )
