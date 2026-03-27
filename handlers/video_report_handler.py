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
    waiting_for_post_selection = State()
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
        
        # Получаем список постов для выбора
        async with db.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT id, title FROM content_plan WHERE status='draft' AND theme='base_expert' ORDER BY id LIMIT 9"
            )
            posts = await cursor.fetchall()
        
        if not posts:
            await message.reply("❌ Нет доступных экспертных постов в плане")
            await state.clear()
            return
        
        # Формируем список для выбора
        post_list = "\n".join([f"{i+1}. {post[1]}" for i, post in enumerate(posts)])
        
        await state.update_data(available_posts=posts)
        
        await message.reply(
            f"✅ Видео получено ({file_size_mb:.1f} МБ)\n\n"
            "🎯 <b>Выберите экспертный пост из плана:</b>\n\n"
            f"{post_list}\n\n"
            "Отправьте номер поста (1-9):",
            parse_mode="HTML"
        )
        
        await state.set_state(VideoReportStates.waiting_for_post_selection)
    
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        await message.reply(f"❌ Ошибка: {e}")
        await state.clear()


@router.message(VideoReportStates.waiting_for_post_selection)
async def select_post(message: Message, state: FSMContext):
    """Выбор поста из плана"""
    
    try:
        choice = message.text.strip()
        
        if not choice.isdigit():
            await message.reply("❌ Отправьте номер поста (цифру)")
            return
        
        choice_num = int(choice) - 1  # 0-based
        
        data = await state.get_data()
        posts = data.get('available_posts', [])
        
        if choice_num < 0 or choice_num >= len(posts):
            await message.reply(f"❌ Неверный номер. Выберите от 1 до {len(posts)}")
            return
        
        selected_post = posts[choice_num]
        post_id, post_title = selected_post
        
        # Получаем полный пост
        async with db.conn.cursor() as cursor:
            await cursor.execute(
                "SELECT body FROM content_plan WHERE id=?",
                (post_id,)
            )
            result = await cursor.fetchone()
        
        if not result:
            await message.reply("❌ Пост не найден")
            return
        
        post_body = result[0]
        
        # Обновляем статус поста
        await db.conn.execute(
            "UPDATE content_plan SET status='published' WHERE id=?",
            (post_id,)
        )
        await db.conn.commit()
        
        # Сохраняем данные поста
        await state.update_data(
            selected_post_id=post_id,
            selected_post_title=post_title,
            selected_post_body=post_body
        )
        
        await message.reply(
            f"✅ <b>Выбран пост:</b> {post_title}\n\n"
            f"<b>Описание:</b>\n{post_body}\n\n"
            "✅ Добавится ватермарк ГЕОРИС\n"
            "✅ Опубликуется в TG и VK\n\n"
            "Публиковать? (Да/Нет)",
            parse_mode="HTML"
        )
        
        await state.set_state(VideoReportStates.waiting_for_confirmation)
    
    except Exception as e:
        logger.error(f"❌ Ошибка выбора поста: {e}")
        await message.reply(f"❌ Ошибка: {e}")
        await state.clear()


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
                data['selected_post_title'],
                data['selected_post_body'],
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
        caption = f"{data['selected_post_body']}\n\n#ГЕОРИС #перепланировка"
        
        tg1 = await publisher.publish_to_telegram(CHANNEL_ID_GEORIS, output_video, caption, data['title'])
        tg2 = await publisher.publish_to_telegram(CHANNEL_ID_DOM_GRAD, output_video, caption, data['title'])
        
        # Обновляем статус
        await db.conn.execute(
            "UPDATE video_reports SET status='published', published_to_tg=?, published_at=? WHERE video_path=?",
            (tg1 or tg2, datetime.now(), output_video)
        )
        await db.conn.commit()
        
        result = f"✅ <b>Видео опубликовано!</b>\n\n"
        result += f"Название: {data['selected_post_title']}\n"
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
