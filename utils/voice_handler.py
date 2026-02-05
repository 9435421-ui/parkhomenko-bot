import os
import aiohttp
import asyncio
from dotenv import load_dotenv

load_dotenv()

class VoiceHandler:
    def __init__(self):
        self.api_key = os.getenv("YANDEX_API_KEY")
        self.folder_id = os.getenv("FOLDER_ID")
        self.url = 'https://stt.api.cloud.yandex.net/speech/v1/stt:recognize'

    async def transcribe(self, file_path: str) -> str:
        """Transcribes audio file to text using Yandex SpeechKit (Async)"""
        if not self.api_key or not self.folder_id:
            print("Yandex API key or Folder ID not found")
            return ""

        try:
            with open(file_path, 'rb') as f:
                audio_data = f.read()

            headers = {
                'Authorization': f'Api-Key {self.api_key}',
            }

            if file_path.endswith('.oga') or file_path.endswith('.ogg'):
                content_type = 'audio/ogg;codecs=opus'
            elif file_path.endswith('.mp3'):
                content_type = 'audio/mpeg'
            else:
                content_type = 'audio/x-wav'

            headers['Content-Type'] = content_type

            params = {
                'lang': 'ru-RU',
                'folderId': self.folder_id
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self.url, headers=headers, params=params, data=audio_data, timeout=30) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get('result', '')
                    else:
                        error_text = await response.text()
                        print(f"Yandex STT API error: {response.status} - {error_text}")
                        return ""

        except Exception as e:
            print(f"Error in transcribe: {e}")
            return ""

    def transcribe_sync(self, file_path: str) -> str:
        """Synchronous wrapper for transcribe"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # Это может случиться в Telebot если он в одном потоке с чем-то асинхронным
            # Но Telebot обычно синхронный.
            import requests
            # fallback to requests for truly sync environment if loop is busy
            return self._transcribe_requests(file_path)

        return loop.run_until_complete(self.transcribe(file_path))

    def _transcribe_requests(self, file_path: str) -> str:
        import requests
        if not self.api_key or not self.folder_id: return ""
        try:
            with open(file_path, 'rb') as f: audio_data = f.read()
            headers = {'Authorization': f'Api-Key {self.api_key}'}
            if file_path.endswith('.oga') or file_path.endswith('.ogg'): content_type = 'audio/ogg;codecs=opus'
            elif file_path.endswith('.mp3'): content_type = 'audio/mpeg'
            else: content_type = 'audio/x-wav'
            headers['Content-Type'] = content_type
            params = {'lang': 'ru-RU', 'folderId': self.folder_id}
            response = requests.post(self.url, headers=headers, params=params, data=audio_data, timeout=30)
            if response.status_code == 200: return response.json().get('result', '')
            return ""
        except: return ""

voice_handler = VoiceHandler()
