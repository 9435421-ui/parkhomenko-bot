"""
Обработчик инвест-калькулятора
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from database.db import db
from config import ADMIN_GROUP_ID
import json
import logging

logger = logging.getLogger(__name__)
router = Router()

@router.callback_query(F.data == "mode:invest")
async def start_invest_mode(callback: CallbackQuery, state: FSMContext):
    """Переход в режим инвест-калькулятора"""
    await state.clear()
    await db.update_user_state(callback.from_user.id, mode="invest")
    await callback.message.answer(
        "💰 <b>Инвест-калькулятор</b>\n\n"
        "Этот инструмент поможет вам оценить, насколько вырастет стоимость вашей недвижимости после грамотной перепланировки.\n\n"
        "Вы можете воспользоваться нашим <b>Mini App</b> (кнопка в меню) для удобного расчета или просто опишите параметры вашей квартиры здесь, и я помогу с оценкой!",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(F.web_app_data)
async def handle_web_app_data(message: Message):
    """Обработка данных из Mini App"""
    try:
        data = json.loads(message.web_app_data.data)
        user = message.from_user
        
        summary = (
            f"💰 <b>Расчет из Инвест-калькулятора (Mini App)</b>\n\n"
            f"👤 Клиент: {user.full_name} (@{user.username or 'id'+str(user.id)})\n"
            f"📍 Город: {data.get('city')}\n"
            f"📏 Площадь: {data.get('area')} м²\n"
            f"🏗 Тип дома: {data.get('houseType')}\n"
            f"🏢 Этаж: {data.get('floor')}\n"
            f"🛠 Изменения: {data.get('changes')}\n"
            f"💵 Бюджет: {data.get('budget')} ₽\n"
        )
        
        # Отправка админу
        await message.bot.send_message(ADMIN_GROUP_ID, summary, parse_mode="HTML")
        
        # Сохранение как лид
        await db.add_lead(
            user_id=user.id,
            name=user.full_name,
            phone="",
            object_type="Инвест-расчет",
            city=data.get('city'),
            status="invest_calc",
            details=f"Площадь: {data.get('area')}, Изменения: {data.get('changes')}, Бюджет: {data.get('budget')}"
        )
        
        await message.answer(
            "✅ Данные вашего расчета получены!\n\n"
            "Юлия Пархоменко проанализирует ваш кейс и свяжется с вами, чтобы подтвердить цифры и обсудить стратегию реализации.",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Error processing web_app_data: {e}")
        await message.answer("Произошла ошибка при обработке данных. Пожалуйста, попробуйте еще раз или напишите параметры текстом.")

@router.message()
async def invest_handler(message: Message, state: FSMContext):
    """
    Обработчик текстовых сообщений в режиме инвест-калькулятора
    """
    user_id = message.from_user.id
    user_state = await db.get_user_state(user_id)
    
    if not user_state or user_state.get("mode") != "invest":
        return

    # Если пользователь пишет текст в этом режиме, перенаправляем его на квиз или предлагаем Mini App
    await message.answer(
        "Для точного расчета инвестиционного потенциала лучше всего воспользоваться нашим Mini App (кнопка в главном меню) "
        "или пройти короткий опрос (кнопка 'Оставить заявку').\n\n"
        "Но я уже передал ваш запрос специалисту, он свяжется с вами!"
    )
    
    # Дублируем сообщение админу как лид
    await message.bot.send_message(
        ADMIN_GROUP_ID, 
        f"💰 <b>Запрос в инвест-режиме:</b>\n\n"
        f"👤 Клиент: {message.from_user.full_name}\n"
        f"📝 Сообщение: {message.text}",
        parse_mode="HTML"
    )
