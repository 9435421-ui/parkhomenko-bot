import aiohttp
import logging
from config import YANDEX_API_KEY, FOLDER_ID

logger = logging.getLogger(__name__)

async def convert_voice_to_text(file_content: bytes) -> str:
    """Отправляет аудио в Yandex SpeechKit и получает текст"""
    url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
    headers = {"Authorization": f"Api-Key {YANDEX_API_KEY}"}
    params = {"folderId": FOLDER_ID, "lang": "ru-RU"}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                url, headers=headers, params=params, data=file_content,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    text = result.get("result", "")
                    logger.info(f"SpeechKit распознал: {text[:100]}")
                    return text
                else:
                    error_data = await response.text()
                    logger.error(f"SpeechKit Error: {response.status} - {error_data}")
                    return "Ошибка расшифровки голоса."
        except Exception as e:
            logger.error(f"Voice conversion failed: {e}")
            return "Произошла ошибка при связи с сервером AI."
