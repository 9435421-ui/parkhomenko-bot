"""
Главное меню - старт квиза
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from keyboards.main_menu import get_main_menu, get_admin_menu
from handlers.quiz import QuizStates
from config import ADMIN_ID

router = Router()

GREETING_TEXT = (
    "🏢 <b>Вас приветствует компания ТЕРИОН!</b>\n\n"
    "Я — Антон, ваш ИИ-помощник по перепланировкам.\n\n"
    "Нажимая кнопку ниже, вы даете согласие на обработку "
    "персональных данных, получение уведомлений и информационную переписку.\n\n"
    "📞 Все консультации носят информационный характер, "
    "финальное решение подтверждает эксперт ТЕРИОН."
)


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext):
    """Старт - показываем приветствие"""
    user_id = message.from_user.id
    
    # Очищаем старые состояния
    await state.clear()
    
    # Проверяем админ
    if str(user_id) == str(ADMIN_ID):
        await message.answer(
            "🎯 <b>Главное меню</b>\n\n"
            "🛠 <b>Создать пост</b> — генерация контента\n"
            "📅 <b>Контент-план</b> — идеи от Скаута\n"
            "👤 <b>Мой профиль</b> — настройки и статистика\n\n"
            "Выберите:",
            reply_markup=get_admin_menu()
        )
    else:
        await message.answer(
            GREETING_TEXT,
            reply_markup=get_main_menu(user_id)
        )


@router.message(F.text == "🛠 Создать пост")
async def create_post_handler(message: Message, state: FSMContext):
    """Создание поста - переход в content"""
    # TODO: перенаправить в content.py
    await message.answer(
        "🛠 <b>Создание поста</b>\n\n"
        "Выберите формат:",
        reply_markup=get_inline_keyboard("create_post")
    )


@router.message(F.text == "📅 Контент-план")
async def content_plan_handler(message: Message, state: FSMContext):
    """Контент-план - запрос идей у Скаута"""
    from agents.scout_agent import scout_agent
    import asyncio
    
    await message.answer("🔍 Скаут ищет идеи...")
    
    try:
        topics = asyncio.run(scout_agent.scout_topics(count=5))
        
        text = "📅 <b>Контент-план</b>\n\n"
        for i, topic in enumerate(topics, 1):
            text += f"{i}. {topic['title']}\n"
            text += f"   💡 {topic['insight']}\n\n"
        
        await message.answer(text, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")


@router.message(F.text == "👤 Мой профиль")
async def profile_handler(message: Message, state: FSMContext):
    """Профиль пользователя"""
    await message.answer(
        "👤 <b>Мой профиль</b>\n\n"
        "📊 Статистика:\n"
        "• Заявок: 0\n"
        "• Консультаций: 0\n\n"
        "🎂 День рождения: не указан\n\n"
        "Настройки в разработке.",
        parse_mode="HTML"
    )


@router.message(F.text == "📝 Записаться на консультацию")
async def quiz_start(message: Message, state: FSMContext):
    """Запуск квиза"""
    from keyboards.main_menu import get_contact_keyboard
    
    await state.clear()
    await message.answer(
        GREETING_TEXT,
        reply_markup=get_contact_keyboard()
    )
    await state.set_state(QuizStates.greeting)


@router.message(F.text == "💬 Задать вопрос")
async def question_handler(message: Message, state: FSMContext):
    """Задать вопрос консультанту"""
    await message.answer(
        "💬 <b>Задайте ваш вопрос</b>\n\n"
        "Наш ИИ-консультант ответит на основе базы знаний "
        "по перепланировкам и согласованию.",
        parse_mode="HTML"
    )


def get_inline_keyboard(action: str):
    """Inline клавиатура для действий"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    markup = InlineKeyboardMarkup()
    
    if action == "create_post":
        markup.add(InlineKeyboardButton("📸 С фото", callback_data="content_with_photo"))
        markup.add(InlineKeyboardButton("📝 Только текст", callback_data="content_text_only"))
        markup.add(InlineKeyboardButton("🎨 Сгенерировать картинку", callback_data="content_gen_image"))
        markup.add(InlineKeyboardButton("◀️ Назад", callback_data="content_back"))
    
    return markup
