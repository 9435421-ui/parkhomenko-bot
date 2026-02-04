from config import YANDEX_API_KEY, YANDEX_FOLDER_ID
import aiohttp
import asyncio
import os

class YandexGPTClient:
    def __init__(self):
        self.api_key = YANDEX_API_KEY
        self.folder_id = YANDEX_FOLDER_ID

    async def generate_text(self, prompt: str) -> str:
        """Генерация текста через Яндекс.ГПТ"""
        url = "https://llm.api.cloud.yandex.net/gpt/v2/generate"
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "general",
            "max_tokens": 1000,
            "temperature": 0.7,
            "top_p": 0.9,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
            "prompt": prompt
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                result = await response.json()
                return result.get("result", "")

    async def transcribe_audio(self, file_path: str) -> str:
        """Транскрибация аудио в текст"""
        url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Transfer-Encoding": "chunked"
        }
        with open(file_path, "rb") as f:
            audio_data = f.read()

        payload = {
            "config": {
                "specification": {
                    "languageCode": "ru-RU",
                    "audioEncoding": "LINEAR16_PCM",
                    "sampleRateHertz": 16000
                }
            }
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, data=audio_data) as response:
                result = await response.json()
                return result.get("result", "")

    async def download_file_by_id(self, file_id: str) -> str:
        """Загрузка файла по file_id из Telegram"""
        from aiogram import Bot
        bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
        file_path = await bot.download_file_by_id(file_id)
        return file_path

# Экземпляр клиента для использования в других модулях
yandex_gpt = YandexGPTClient()
