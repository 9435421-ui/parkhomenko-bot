import os
import logging
import aiohttp
import asyncio
import base64
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class YandexArtClient:
    """Яндекс АРТ для генерации изображений"""
    def __init__(self, api_key: str, folder_id: str):
        self.api_key = api_key
        self.folder_id = folder_id
        self.headers = {
            "Authorization": f"Api-Key {api_key}",
            "x-folder-id": folder_id
        }

    async def generate(self, prompt: str) -> Optional[str]:
        """Генерация изображения, возвращает base64"""
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGenerationAsync"
        payload = {
            "modelUri": f"art://{self.folder_id}/yandex-art/latest",
            "generationOptions": {
                "seed": 0,
                "aspectRatio": {"widthRatio": 1, "heightRatio": 1}
            },
            "messages": [{"role": "user", "text": prompt}]
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=payload) as resp:
                    if resp.status != 200:
                        logger.error(f"YandexArt error {resp.status}: {await resp.text()}")
                        return None
                    
                    data = await resp.json()
                    op_id = data.get("id")
                    if not op_id: return None
                    
                    # Ожидание результата
                    op_base = "https://llm.api.cloud.yandex.net"
                    for _ in range(30):
                        await asyncio.sleep(2)
                        async with session.get(f"{op_base}/operations/{op_id}", headers=self.headers) as check:
                            res = await check.json()
                            if res.get("done"):
                                return res.get("response", {}).get("image")
            return None
        except Exception as e:
            logger.error(f"YandexArt exception: {e}")
            return None

class RouterAIClient:
    """RouterAI для текстов и изображений (Gemini/Claude)"""
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://router.ai/api/v1" # Пример URL, уточнить если другой
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async def generate_image_gemini(self, prompt: str) -> Optional[str]:
        """Генерация изображения через Gemini 1.5 Flash (через RouterAI)"""
        url = f"{self.base_url}/images/generations"
        payload = {
            "model": "gemini-1.5-flash", # Или актуальная модель для генерации
            "prompt": prompt,
            "n": 1,
            "size": "1024x1024",
            "response_format": "b64_json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data['data'][0]['b64_json']
            return None
        except Exception as e:
            logger.error(f"RouterAI Image exception: {e}")
            return None

class ImageAgent:
    """Централизованный агент генерации изображений"""
    def __init__(self):
        self.yandex_art = None
        self.router_ai = None
        
        y_key = os.getenv("YANDEX_API_KEY")
        f_id = os.getenv("FOLDER_ID")
        r_key = os.getenv("ROUTER_API_KEY")
        
        if y_key and f_id:
            self.yandex_art = YandexArtClient(y_key, f_id)
        if r_key:
            self.router_ai = RouterAIClient(r_key)

    def build_image_prompt(self, post_type: str, text: str) -> str:
        base_style = "Photorealistic, professional architectural photography, high quality, 4k. "
        prompts = {
            'news': f"Modern office building with blueprints, legal documents, urban style. {text[:100]}",
            'fact': f"Educational concept, light bulb, building plan, magnifying glass over documents. {text[:100]}",
            'seasonal': f"House exterior during appropriate season, cozy lighting, real estate concept. {text[:100]}",
            'case': f"Before and after floor plan transformation, modern interior design, renovation process. {text[:100]}",
            'offer': f"Friendly architect consulting client, signing contract, keys to new property. {text[:100]}"
        }
        prompt = prompts.get(post_type, f"Real estate redevelopment concept. {text[:100]}")
        return base_style + prompt

    async def generate_image(self, prompt: str, provider: str = "auto") -> Optional[bytes]:
        """
        Генерация изображения. Возвращает bytes.
        """
        b64_data = None
        
        if provider == "yandex" and self.yandex_art:
            b64_data = await self.yandex_art.generate(prompt)
        elif provider == "gemini" and self.router_ai:
            b64_data = await self.router_ai.generate_image_gemini(prompt)
        else:
            # Auto-fallback
            if self.yandex_art:
                b64_data = await self.yandex_art.generate(prompt)
            if not b64_data and self.router_ai:
                b64_data = await self.router_ai.generate_image_gemini(prompt)
                
        if b64_data:
            try:
                return base_base64_to_bytes(b64_data)
            except:
                return None
        return None

def base_base64_to_bytes(b64_string: str) -> bytes:
    """Конвертация base64 в bytes"""
    if "," in b64_string:
        b64_string = b64_string.split(",")[1]
    return base64.b64decode(b64_string)

image_generator = ImageAgent()
