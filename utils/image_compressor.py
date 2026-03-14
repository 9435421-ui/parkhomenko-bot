"""
Утилита для сжатия и обработки изображений.
Используется для подготовки фото объектов к публикации в ТГ и ВК.
"""
import os
import logging
from PIL import Image
from PIL import ImageOps
from io import BytesIO
from typing import Optional, Tuple
import asyncio

logger = logging.getLogger(__name__)


# Настройки для разных платформ
TELEGRAM_MAX_SIZE = (2048, 2048)  # ТГ лимит
TELEGRAM_QUALITY = 85

VK_MAX_SIZE = (2560, 2560)  # ВК рекомендация
VK_QUALITY = 90


def get_image(image_path: str) -> dict:
    """Получить информацию об изображении"""
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            format_name = img.format
            file_size = os.path.getsize(image_path)
            
            return {
                'width': width,
                'height': height,
                'format': format_name,
                'size_bytes': file_size,
                'size_mb': round(file_size / (1024 * 1024), 2)
            }
    except Exception as e:
        logger.error(f"Ошибка получения информации о фото: {e}")
        return {}


def compress_image(
    image_path: str,
    output_path: Optional[str] = None,
    max_size: Tuple[int, int] = TELEGRAM_MAX_SIZE,
    quality: int = TELEGRAM_QUALITY,
    format: str = 'JPEG'
) -> Optional[str]:
    """
    Сжимает изображение для публикации.
    
    Args:
        image_path: Путь к исходному изображению
        output_path: Путь для сохранения (если None - перезаписывает)
        max_size: Максимальный размер (ширина, высота)
        quality: Качество сжатия (1-100)
        format: Формат выходного изображения
    
    Returns:
        Путь к сжатому изображению или None при ошибке
    """
    try:
        with Image.open(image_path) as img:
            # Конвертация в RGB если нужно
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Изменение размера с сохранением пропорций
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Автоматическая ориентация (для фото с телефонов)
            img = ImageOps.exif_transpose(img)
            
            # Оптимизация
            output_buffer = BytesIO()
            img.save(
                output_buffer,
                format=format,
                quality=quality,
                optimize=True
            )
            
            # Сохраняем результат
            if output_path is None:
                output_path = image_path
            
            with open(output_path, 'wb') as f:
                f.write(output_buffer.getvalue())
            
            # Логируем результат
            original_size = os.path.getsize(image_path)
            new_size = os.path.getsize(output_path)
            compression_ratio = round((1 - new_size / original_size) * 100, 1)
            
            logger.info(f"📸 Фото сжато: {compression_ratio}% ({original_size} → {new_size} байт)")
            
            return output_path
            
    except Exception as e:
        logger.error(f"❌ Ошибка сжатия фото: {e}")
        return None


async def compress_image_async(
    image_path: str,
    output_path: Optional[str] = None,
    max_size: Tuple[int, int] = TELEGRAM_MAX_SIZE,
    quality: int = TELEGRAM_QUALITY
) -> Optional[str]:
    """Асинхронная версия сжатия"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: compress_image(image_path, output_path, max_size, quality)
    )


def prepare_for_telegram(image_path: str) -> Optional[str]:
    """Подготовить фото для Telegram"""
    return compress_image(
        image_path,
        max_size=TELEGRAM_MAX_SIZE,
        quality=TELEGRAM_QUALITY
    )


def prepare_for_vk(image_path: str) -> Optional[str]:
    """Подготовить фото для ВКонтакте"""
    return compress_image(
        image_path,
        max_size=VK_MAX_SIZE,
        quality=VK_QUALITY
    )


def create_thumbnail(image_path: str, size: Tuple[int, int] = (300, 300)) -> Optional[str]:
    """
    Создать превью изображения.
    
    Args:
        image_path: Путь к изображению
        size: Размер превью
    
    Returns:
        Путь к превью или None при ошибке
    """
    try:
        output_path = f"{os.path.splitext(image_path)[0]}_thumb{os.path.splitext(image_path)[1]}"
        
        with Image.open(image_path) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS)
            img.save(output_path, quality=75, optimize=True)
        
        return output_path
        
    except Exception as e:
        logger.error(f"Ошибка создания превью: {e}")
        return None


def get_file_extension(mime_type: str) -> str:
    """Получить расширение файла по MIME-типу"""
    extensions = {
        'image/jpeg': '.jpg',
        'image/png': '.png',
        'image/gif': '.gif',
        'image/webp': '.webp'
    }
    return extensions.get(mime_type, '.jpg')


def validate_image(image_path: str) -> bool:
    """Проверить что файл это изображение"""
    try:
        with Image.open(image_path) as img:
            return img.format in ('JPEG', 'PNG', 'GIF', 'WEBP')
    except:
        return False
