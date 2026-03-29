"""
handlers/video_handler_v2.py
Улучшенный обработчик видео с обработкой и генерацией контента
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
from services.video_editor import editor
from services.video_publisher import VideoPublisher
from services.content_generator import generator

logger = logging.getLogger(__name__)
router = Router()

class VideoProcessingStates(StatesGroup):
    """Состояния при обработке видео"""
    waiting_for_video = State()
    waiting_for_topic = State()
    processing = State()


@router.message(Command("video"))
async def cmd_video_v2(message: Message, state: FSMContext):
    """Команда /video - загрузить и обработать видео"""
    
    # Только админ
    if message.from_user.id != 5818701786:
        await message.reply("❌ Только администратор")
        return
    
    await message.reply(
        "🎬 <b>ВИДЕО-ПРОДАКШЕН ГЕОРИС</b>\n\n"
        "Отправьте видео (MP4, MOV или другой формат)\n\n"
        "Видео будет:\n"
        "✅ Очищено от шума\n"
        "✅ Удалены паузы\n"
        "✅ Ускорено (1.2x)\n"
        "✅ Добавлен ватермарк ГЕОРИС\n"
        "✅ Опубликовано в TG и VK",
        parse_mode="HTML"
    )
    
    await state.set_state(VideoProcessingStates.waiting_for_video)


@router.message(VideoProcessingStates.waiting_for_video, F.video)
async def receive_video_v2(message: Message, state: FSMContext, bot):
    """Получить видео и запустить обработку"""
    
    try:
        await message.reply("⏳ Загружаю видео...")
        
        # Создаём папки
        raw_dir = Path("/root/PARKHOMENKO_BOT/videos/raw")
        raw_dir.mkdir(parents=True, exist_ok=True)
        
        # Загружаем видео
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        video_filename = f"raw_{timestamp}.mp4"
        video_path = raw_dir / video_filename
        
        file_info = message.video
        file = await bot.get_file(file_info.file_id)
        await bot.download_file(file.file_path, str(video_path))
        
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        
        logger.info(f"✅ Видео получено: {video_filename} ({file_size_mb:.1f} МБ)")
        
        await state.update_data(
            video_path=str(video_path),
            file_size_mb=file_size_mb,
            original_filename=video_filename
        )
        
        await message.reply(
            f"✅ Видео получено ({file_size_mb:.1f} МБ)\n\n"
            "Напишите <b>тему/название</b> видео\n\n"
            "Например: <code>Согласование перепланировки в новостройке</code>",
            parse_mode="HTML"
        )
        
        await state.set_state(VideoProcessingStates.waiting_for_topic)
    
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки: {e}")
        await message.reply(f"❌ Ошибка: {e}")
        await state.clear()


@router.message(VideoProcessingStates.waiting_for_topic)
async def receive_topic(message: Message, state: FSMContext, bot):
    """Получить тему видео и запустить обработку"""
    
    topic = message.text.strip()
    
    if len(topic) < 3:
        await message.reply("❌ Тема слишком короткая (минимум 3 символа)")
        return
    
    await message.reply(
        "⏳ <b>НАЧИНАЮ ОБРАБОТКУ</b>\n\n"
        "Это может занять несколько минут...\n"
        "🔄 Шаги:\n"
        "1️⃣ Уменьшение шума\n"
        "2️⃣ Удаление пауз\n"
        "3️⃣ Ускорение видео\n"
        "4️⃣ Добавление ватермарка\n"
        "5️⃣ Публикация",
        parse_mode="HTML"
    )
    
    data = await state.get_data()
    
    try:
        input_video = data['video_path']
        
        # Этап 1: Полная обработка видео
        processed_dir = Path("/root/PARKHOMENKO_BOT/videos/processed")
        processed_dir.mkdir(parents=True, exist_ok=True)
        processed_video = str(processed_dir / f"processed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
        
        logger.info("🔄 Запускаю полную обработку видео...")
        success = await editor.process_full(
            input_video,
            processed_video,
            remove_silence=True,
            reduce_noise=True,
            speed_up=True,
            speed=1.2
        )
        
        if not success:
            raise Exception("Ошибка обработки видео")
        
        # Этап 2: Добавляем ватермарк
        final_dir = Path("/root/PARKHOMENKO_BOT/videos/final")
        final_dir.mkdir(parents=True, exist_ok=True)
        final_video = str(final_dir / f"final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4")
        
        logger.info("🎨 Добавляю ватермарк...")
        success = await processor.add_watermark(processed_video, final_video)
        
        if not success:
            raise Exception("Ошибка добавления ватермарка")
        
        # Этап 3: Генерируем превью
        thumbnails_dir = Path("/root/PARKHOMENKO_BOT/videos/thumbnails")
        thumbnails_dir.mkdir(parents=True, exist_ok=True)
        thumbnail_path = str(thumbnails_dir / f"thumb_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
        
        await processor.generate_thumbnail(final_video, thumbnail_path)
        
        # Этап 4: Сохраняем в БД
        await db.conn.execute(
            """
            INSERT INTO video_reports 
            (title, description, video_path, thumbnail_path, file_size_mb, status, admin_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                topic,
                f"Видео-репортаж: {topic}",
                final_video,
                thumbnail_path,
                os.path.getsize(final_video) / (1024 * 1024),
                'ready',
                message.from_user.id,
                datetime.now()
            )
        )
        await db.conn.commit()
        
        # Этап 5: Публикуем
        logger.info("📤 Публикую видео...")
        publisher = VideoPublisher(bot=bot)
        
        caption = f"<b>{topic}</b>\n\n#ГЕОРИС #перепланировка #согласование"
        
        tg1 = await publisher.publish_to_telegram(
            CHANNEL_ID_GEORIS,
            final_video,
            caption=caption,
            title=topic
        )
        
        tg2 = await publisher.publish_to_telegram(
            CHANNEL_ID_DOM_GRAD,
            final_video,
            caption=caption,
            title=topic
        )
        
        # Обновляем статус
        await db.conn.execute(
            "UPDATE video_reports SET status='published', published_to_tg=?, published_at=? WHERE video_path=?",
            (tg1 or tg2, datetime.now(), final_video)
        )
        await db.conn.commit()
        
        # Итоговое сообщение
        result = f"""
✅ <b>ВИДЕО ОБРАБОТАНО И ОПУБЛИКОВАНО!</b>

📹 Название: {topic}
📊 Размер: {os.path.getsize(final_video) / (1024 * 1024):.1f} МБ
📱 TG каналы: {'✅' if (tg1 or tg2) else '❌'}

🎬 Обработка включала:
  ✅ Удаление шума
  ✅ Удаление пауз
  ✅ Ускорение 1.2x
  ✅ Ватермарк ГЕОРИС
        """
        
        if os.path.exists(thumbnail_path):
            with open(thumbnail_path, 'rb') as thumb:
                await message.reply_photo(
                    photo=FSInputFile(thumbnail_path),
                    caption=result,
                    parse_mode="HTML"
                )
        else:
            await message.reply(result, parse_mode="HTML")
        
        logger.info(f"✅ Видео успешно опубликовано: {topic}")
    
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await message.reply(f"❌ Ошибка при обработке: {str(e)}")
    
    await state.clear()
