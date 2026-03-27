"""
services/video_processor.py
Обработка видео: добавление ватермарка, сжатие, генерация превью
"""

import os
import asyncio
import logging
from pathlib import Path
from datetime import datetime
import subprocess
import json
from typing import Optional

logger = logging.getLogger(__name__)

class VideoProcessor:
    """Обработка видео (FFmpeg)"""
    
    def __init__(self, project_root: str = "/root/PARKHOMENKO_BOT"):
        self.project_root = Path(project_root)
        self.videos_dir = self.project_root / "videos"
        self.watermarks_dir = self.project_root / "watermarks"
        self.fonts_dir = self.project_root / "templates" / "fonts"
        self.font_path = self.fonts_dir / "Roboto-Bold.ttf"
        
        # Проверяем FFmpeg
        self.ffmpeg_available = self._check_ffmpeg()
        
        if self.ffmpeg_available:
            logger.info("✅ FFmpeg доступен")
        else:
            logger.warning("⚠️ FFmpeg не установлен")
    
    def _check_ffmpeg(self) -> bool:
        """Проверить есть ли FFmpeg"""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    async def add_watermark(
        self, 
        input_path: str, 
        output_path: str,
        watermark_path: Optional[str] = None
    ) -> bool:
        """Добавить ватермарк на видео"""
        if not self.ffmpeg_available:
            logger.warning("FFmpeg не доступен, копирую видео")
            try:
                with open(input_path, 'rb') as src:
                    with open(output_path, 'wb') as dst:
                        dst.write(src.read())
                return True
            except Exception as e:
                logger.error(f"Ошибка копирования: {e}")
                return False
        
        if watermark_path is None:
            watermark_path = str(self.watermarks_dir / "watermark.png")
        
        try:
            if os.path.exists(watermark_path):
                cmd = [
                    "ffmpeg", "-i", input_path,
                    "-i", watermark_path,
                    "-filter_complex", "[0:v][1:v]overlay=main_w-overlay_w-10:main_h-overlay_h-10",
                    "-c:a", "aac", "-c:v", "libx264", "-preset", "fast",
                    "-y", output_path
                ]
            else:
                cmd = [
                    "ffmpeg", "-i", input_path,
                    "-c:v", "libx264", "-preset", "fast",
                    "-c:a", "aac", "-y", output_path
                ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"✅ Видео обработано")
                return True
            else:
                logger.error(f"❌ FFmpeg ошибка")
                return False
        
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False
    
    async def generate_thumbnail(
        self, 
        video_path: str, 
        output_path: str,
        timestamp: str = "00:00:01"
    ) -> bool:
        """Генерировать превью видео"""
        if not self.ffmpeg_available:
            return False
        
        try:
            cmd = [
                "ffmpeg", "-i", video_path,
                "-ss", timestamp,
                "-vframes", "1",
                "-vf", "scale=320:180",
                "-y", output_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            return process.returncode == 0
        except:
            return False

processor = VideoProcessor()
