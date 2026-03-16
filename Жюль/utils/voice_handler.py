"""
Транскрибация голосовых сообщений для админ-панели (Yandex SpeechKit).
"""
import os
import logging
import aiohttp

logger = logging.getLogger(__name__)

async def convert_voice_to_text(file_content: bytes) -> str | None:
    """
    Транскрибирует голосовое сообщение в текст через Yandex SpeechKit.
    file_content: бинарные данные аудиофайла (OGG Opus).
    """
    api_key = os.getenv("YANDEX_API_KEY")
    if not api_key:
        logger.debug("YANDEX_API_KEY не задан — транскрибация отключена")
        return None

    url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
    headers = {"Authorization": f"Api-Key {api_key}"}
    params = {"lang": "ru-RU", "format": "oggopus"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=headers,
                params=params,
                data=file_content,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.warning(f"SpeechKit STT {resp.status}: {text[:200]}")
                    return None
                data = await resp.json()
                return (data.get("result") or "").strip() or None
    except Exception as e:
        logger.warning(f"Ошибка транскрибации: {e}")
        return None
