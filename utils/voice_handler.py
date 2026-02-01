import os
import requests
from dotenv import load_dotenv

load_dotenv()

class VoiceHandler:
    def __init__(self):
        self.api_key = os.getenv("YANDEX_API_KEY")
        self.folder_id = os.getenv("FOLDER_ID")
        self.url = 'https://stt.api.cloud.yandex.net/speech/v1/stt:recognize'

    def transcribe(self, file_path: str) -> str:
        """Transcribes audio file to text using Yandex SpeechKit"""
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

            response = requests.post(self.url, headers=headers, params=params, data=audio_data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                return result.get('result', '')
            else:
                print(f"Yandex STT API error: {response.status_code} - {response.text}")
                return ""

        except Exception as e:
            print(f"Error in transcribe: {e}")
            return ""

voice_handler = VoiceHandler()
