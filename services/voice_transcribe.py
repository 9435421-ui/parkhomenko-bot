"""
Транскрибация голосовых сообщений для квиза (Yandex SpeechKit).
В заявку сохраняется текст результата.
"""
import os
import logging
import aiohttp

logger = logging.getLogger(__name__)


async def transcribe_voice(voice_bytes: bytes, bot=None, file_id: str = None) -> str | None:
    """
    Транскрибирует голосовое сообщение в текст (русский).
    voice_bytes: OGG-аудио от Telegram или путь не нужен если передаём file_id и bot.
    Если передан file_id и bot — сначала скачиваем файл.
    Возвращает текст или None при ошибке.
    """
    if bot and file_id:
        try:
            f = await bot.get_file(file_id)
            voice_bytes = await bot.download_file(f.file_path)
            if hasattr(voice_bytes, "read"):
                voice_bytes = voice_bytes.read()
        except Exception as e:
            logger.warning(f"Не удалось скачать голосовое: {e}")
            return None

    api_key = os.getenv("YANDEX_API_KEY")
    if not api_key:
        logger.debug("YANDEX_API_KEY не задан — транскрибация отключена")
        return None

    url = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
    headers = {"Authorization": f"Api-Key {api_key}"}
    # Telegram голосовые — OGG Opus
    params = {"lang": "ru-RU", "format": "oggopus"}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=headers,
                params=params,
                data=voice_bytes,
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
