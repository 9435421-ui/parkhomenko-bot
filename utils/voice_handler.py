import aiohttp
import logging
from config import YANDEX_API_KEY, FOLDER_ID, BOT_TOKEN

async def transcribe(file_id: str) -> str:
    """Транскрипция голосового сообщения через Yandex SpeechKit"""

    # 1. Получаем путь к файлу в Telegram
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}") as resp:
                data = await resp.json()
                if not data.get("ok"):
                    return ""
                file_path = data["result"]["file_path"]

            # 2. Скачиваем файл
            async with session.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}") as resp:
                voice_data = await resp.read()

            # 3. Отправляем в Yandex SpeechKit
            url = f"https://stt.api.cloud.yandex.net/speech/v1/stt:recognize?folderId={FOLDER_ID}"
            headers = {"Authorization": f"Api-Key {YANDEX_API_KEY}"}

            async with session.post(url, headers=headers, data=voice_data) as resp:
                result = await resp.json()
                if result.get("result"):
                    return result["result"]
    except Exception as e:
        logging.error(f"STT Error: {e}")

    return ""
