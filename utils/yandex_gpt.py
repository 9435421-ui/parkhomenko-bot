from config import YANDEX_API_KEY, YANDEX_FOLDER_ID
from aiogram import Bot
from yandexcloud import YCClient
from yandexcloud.sdk import Config
from yandexcloud.ai.gpt.v2 import GPTService
from yandexcloud.ai.gpt.v2.models import (
    GenerateOptions,
    GenerateRequest,
    GenerateResult,
    TranscriptionOptions,
    TranscriptionRequest,
    TranscriptionResult,
)
import asyncio
import os

class YandexGPTClient:
    def __init__(self):
        self.bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
        self.client = YCClient(
            Config(
                api_key=YANDEX_API_KEY,
                folder_id=YANDEX_FOLDER_ID
            )
        )
        self.gpt_service = GPTService(self.client)

    async def generate_text(self, prompt: str) -> str:
        """Генерация текста через Яндекс.ГПТ"""
        options = GenerateOptions(
            model="general",
            max_tokens=1000,
            temperature=0.7,
            top_p=0.9,
            frequency_penalty=0.0,
            presence_penalty=0.0
        )
        request = GenerateRequest(
            prompt=prompt,
            options=options
        )
        response: GenerateResult = await self.gpt_service.generate(request)
        return response.result

    async def transcribe_audio(self, file_path: str) -> str:
        """Транскрибация аудио в текст"""
        with open(file_path, "rb") as f:
            audio_data = f.read()

        options = TranscriptionOptions(
            model="general",
            language="ru-RU",
            sample_rate=16000
        )
        request = TranscriptionRequest(
            audio=audio_data,
            options=options
        )
        response: TranscriptionResult = await self.gpt_service.transcribe(request)
        return response.result

    async def download_file_by_id(self, file_id: str) -> str:
        """Загрузка файла по file_id из Telegram"""
        file_path = await self.bot.download_file_by_id(file_id)
        return file_path

# Экземпляр клиента для использования в других модулях
yandex_gpt = YandexGPTClient()