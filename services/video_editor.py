"""
services/video_editor.py
Продвинутая обработка видео: шум, паузы, скорость
"""

import os
import asyncio
import logging
from pathlib import Path
import subprocess

logger = logging.getLogger(__name__)

class VideoEditor:
    """Продвинутое редактирование видео"""
    
    def __init__(self):
        self.ffmpeg_available = self._check_ffmpeg()
        self.ffprobe_available = self._check_ffprobe()
    
    def _check_ffmpeg(self) -> bool:
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
            return True
        except:
            return False
    
    def _check_ffprobe(self) -> bool:
        try:
            subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=5)
            return True
        except:
            return False
    
    async def remove_silence(
        self, 
        input_video: str, 
        output_video: str,
        silence_duration: float = 0.5,
        silence_threshold: float = -40
    ) -> bool:
        """
        Удалить паузы (silence) из видео
        
        Args:
            input_video: путь к видео
            output_video: путь выхода
            silence_duration: минимальная длина паузы в секундах
            silence_threshold: порог громкости в dB
        
        Returns:
            True если успешно
        """
        if not self.ffmpeg_available:
            logger.warning("FFmpeg не доступен")
            return False
        
        try:
            # Используем фильтр silenceremove для удаления пауз
            cmd = [
                "ffmpeg",
                "-i", input_video,
                "-af", f"silenceremove=1:0:{silence_threshold}dB:1:{silence_duration}:{silence_threshold}dB",
                "-c:v", "libx264",
                "-preset", "fast",
                "-y", output_video
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"✅ Паузы удалены: {output_video}")
                return True
            else:
                logger.error("❌ Ошибка удаления пауз")
                return False
        
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False
    
    async def reduce_noise(
        self, 
        input_video: str, 
        output_video: str
    ) -> bool:
        """
        Уменьшить шум в видео
        
        Args:
            input_video: путь к видео
            output_video: путь выхода
        
        Returns:
            True если успешно
        """
        if not self.ffmpeg_available:
            return False
        
        try:
            # Используем фильтр anlmdn для уменьшения шума
            cmd = [
                "ffmpeg",
                "-i", input_video,
                "-af", "anlmdn=f=13:t=0.002:tr=1:om=o",
                "-c:v", "libx264",
                "-preset", "fast",
                "-y", output_video
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"✅ Шум уменьшен: {output_video}")
                return True
            else:
                logger.error("❌ Ошибка уменьшения шума")
                return False
        
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False
    
    async def speed_up_video(
        self, 
        input_video: str, 
        output_video: str,
        speed: float = 1.25  # 1.25x ускорение
    ) -> bool:
        """
        Ускорить видео
        
        Args:
            input_video: путь к видео
            output_video: путь выхода
            speed: множитель скорости (1.25 = 125%)
        
        Returns:
            True если успешно
        """
        if not self.ffmpeg_available:
            return False
        
        try:
            # Используем setpts для ускорения видео
            cmd = [
                "ffmpeg",
                "-i", input_video,
                "-filter:v", f"setpts=PTS/{speed}",
                "-filter:a", f"atempo={speed}",
                "-c:v", "libx264",
                "-preset", "fast",
                "-y", output_video
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"✅ Видео ускорено ({speed}x): {output_video}")
                return True
            else:
                logger.error("❌ Ошибка ускорения")
                return False
        
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False
    
    async def process_full(
        self, 
        input_video: str, 
        output_video: str,
        remove_silence: bool = True,
        reduce_noise: bool = True,
        speed_up: bool = True,
        speed: float = 1.25
    ) -> bool:
        """
        Полная обработка видео (все фильтры)
        """
        if not self.ffmpeg_available:
            logger.warning("FFmpeg не доступен")
            return False
        
        try:
            # Построим фильтр цепочку
            audio_filters = []
            video_filters = []
            
            if reduce_noise:
                audio_filters.append("anlmdn=f=13:t=0.002:tr=1:om=o")
            
            if remove_silence:
                audio_filters.append(f"silenceremove=1:0:-40dB:1:0.5:-40dB")
            
            if speed_up:
                audio_filters.append(f"atempo={speed}")
                video_filters.append(f"setpts=PTS/{speed}")
            
            audio_filter_str = ",".join(audio_filters) if audio_filters else None
            video_filter_str = ",".join(video_filters) if video_filters else None
            
            cmd = ["ffmpeg", "-i", input_video]
            
            if audio_filter_str:
                cmd.extend(["-af", audio_filter_str])
            
            if video_filter_str:
                cmd.extend(["-filter:v", video_filter_str])
            
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "fast",
                "-c:a", "aac",
                "-y", output_video
            ])
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"✅ Видео полностью обработано: {output_video}")
                return True
            else:
                logger.error("❌ Ошибка полной обработки")
                return False
        
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False

editor = VideoEditor()
