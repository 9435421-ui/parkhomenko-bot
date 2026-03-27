"""
handlers/video_report_handler.py
Обработка видео-репортажей
"""
import os
import logging
from datetime import datetime
from pathlib import Path
from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import CHANNEL_ID_GEORIS, CHANNEL_ID_DOM_GRAD
from database.db import db
from services.video_processor import processor
from services.video_publisher import VideoPublisher

logger = logging.getLogger(__name__)
router = Router()

class VideoReportStates(StatesGroup):
    """Состояния видео-репортажа"""
    waiting_for_video = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_confirmation = State()


@router.message(Command("video"))
async def cmd_video(message: Message, state: FSMContext):
    """Команда /video"""
    
    # Только админ
    if message.from_user.id != 5818701786:
        await message.reply("❌ Только админ")
        return
    
    await message.reply(
        "🎬 <b>Видео-репортаж</b>\n\n"
        "Отправьте видео (из галереи или файлом)\n\n"
        "✅ Добавится ватермарк ГЕОРИС\n"
        "✅ Опубликуется в TG и VK",
        parse_mode="HTML"
    )
    
    await state.set_state(VideoReportStates.waiting_for_video)


@router.message(VideoReportStates.waiting_for_video, F.video)
async def receive_video(message: Message, state: FSMContext, bot):
    """Получить видео"""
    
    try:
        raw_dir = Path("/root/PARKHOMENKO_BOT/videos/raw")
        raw_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_filename = f"video_{timestamp}.mp4"
        video_path = raw_dir / video_filename
        
        # Скачиваем видео
        file_info = message.video
        file = await bot.get_file(file_info.file_id)
        await bot.download_file(file.file_path, str(video_path))
        
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        duration = file_info.duration if hasattr(file_info, 'duration') else 0
        
        logger.info(f"✅ Видео получено: {video_filename} ({file_size_mb:.1f} МБ)")
        
        await state.update_data(
            video_path=str(video_path),
            file_size_mb=file_size_mb,
            duration=duration
        )
        
        await message.reply(
            f"✅ Видео получено ({file_size_mb:.1f} МБ)\n\n"
            "Напишите <b>название</b> видео",
            parse_mode="HTML"
        )
        
        await state.set_state(VideoReportStates.waiting_for_title)
    
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await message.reply(f"❌ Ошибка: {e}")
        await state.clear()


@router.message(VideoReportStates.waiting_for_title)
async def receive_title(message: Message, state: FSMContext):
    """Получить название"""
    
    title = message.text.strip()
    
    if len(title) < 3:
        await message.reply("❌ Название слишком короткое")
        return
    
    await state.update_data(title=title)
    
    await message.reply(
        f"✅ Название: <b>{title}</b>\n\n"
        "Напишите <b>описание</b> видео",
        parse_mode="HTML"
    )
    
    await state.set_state(VideoReportStates.waiting_for_description)


@router.message(VideoReportStates.waiting_for_description)
async def receive_description(message: Message, state: FSMContext):
    """Получить описание"""
    
    description = message.text.strip()
    
    if len(description) < 5:
        await message.reply("❌ Описание слишком короткое")
        return
    
    await state.update_data(description=description)
    
    data = await state.get_data()
    
    await message.reply(
        f"📋 <b>Проверка:</b>\n\n"
        f"Название: {data['title']}\n"
        f"Размер: {data['file_size_mb']:.1f} МБ\n\n"
        f"Описание: {description}\n\n"
        "✅ Добавится ватермарк ГЕОРИС\n"
        "✅ Опубликуется в TG и VK\n\n"
        "Публиковать? (Да/Нет)",
        parse_mode="HTML"
    )
    
    await state.set_state(VideoReportStates.waiting_for_confirmation)


@router.message(VideoReportStates.waiting_for_confirmation, F.text.lower() == "да")
async def confirm_publish(message: Message, state: FSMContext, bot):
    """Опубликовать"""
    
    await message.reply("⏳ Обрабатываю видео...")
    
    data = await state.get_data()
    
    try:
        input_video = data['video_path']
        processed_dir = Path("/root/PARKHOMENKO_BOT/videos/processed")
        processed_dir.mkdir(parents=True, exist_ok=True)
        
        output_video = str(processed_dir / f"processed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
        
        # Обрабатываем видео
        logger.info(f"Обрабатываю: {input_video}")
        success = await processor.add_watermark(input_video, output_video)
        
        if not success:
            raise Exception("Ошибка FFmpeg")
        
        # Сохраняем в БД
        await db.conn.execute(
            """
            INSERT INTO video_reports 
            (title, description, video_path, duration_seconds, file_size_mb, status, admin_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data['title'],
                data['description'],
                output_video,
                data['duration'],
                data['file_size_mb'],
                'processed',
                message.from_user.id,
                datetime.now()
            )
        )
        await db.conn.commit()
        
        # Публикуем
        publisher = VideoPublisher(bot=bot)
        caption = f"{data['description']}\n\n#ГЕОРИС #перепланировка"
        
        tg1 = await publisher.publish_to_telegram(CHANNEL_ID_GEORIS, output_video, caption, data['title'])
        tg2 = await publisher.publish_to_telegram(CHANNEL_ID_DOM_GRAD, output_video, caption, data['title'])
        
        # Обновляем статус
        await db.conn.execute(
            "UPDATE video_reports SET status='published', published_to_tg=?, published_at=? WHERE video_path=?",
            (tg1 or tg2, datetime.now(), output_video)
        )
        await db.conn.commit()
        
        result = f"✅ <b>Видео опубликовано!</b>\n\n"
        result += f"Название: {data['title']}\n"
        result += f"TG каналы: {'✅' if (tg1 or tg2) else '❌'}\n"
        
        await message.reply(result, parse_mode="HTML")
        
        logger.info(f"✅ Видео опубликовано: {data['title']}")
    
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await message.reply(f"❌ Ошибка: {str(e)}")
    
    await state.clear()


@router.message(VideoReportStates.waiting_for_confirmation, F.text.lower() == "нет")
async def cancel_publish(message: Message, state: FSMContext):
    """Отменить"""
    await message.reply("❌ Отменено")
    await state.clear()


@router.message(Command("video_list"))
async def cmd_video_list(message: Message):
    """Список видео"""
    
    try:
        async with db.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT id, title, status, published_to_tg FROM video_reports ORDER BY created_at DESC LIMIT 5"
            )
            videos = await cursor.fetchall()
        
        if not videos:
            await message.reply("📭 Видео нет")
            return
        
        text = "📹 <b>Последние видео:</b>\n\n"
        for v in videos:
            vid_id, title, status, tg = v
            text += f"#{vid_id}: {title[:40]}\n"
            text += f"Статус: {status} | TG: {'✅' if tg else '❌'}\n\n"
        
        await message.reply(text, parse_mode="HTML")
    
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")
