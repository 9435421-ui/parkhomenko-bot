import aiohttp
import json
import base64
from config import ROUTER_AI_KEY

class ImageGenerator:
    def __init__(self):
        self.api_key = ROUTER_AI_KEY
        self.base_url = "https://routerai.ru/api/v1"
        self.model = "flux-1-dev"

    async def generate_image(self, prompt_context: str) -> bytes:
        """Генерация изображения через RouterAI (flux-1-dev)"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Эталонный промпт из ТЗ v2.6
        reference_prompt = (
            "Professional architectural 3D visualization of a modern apartment renovation, "
            "open space kitchen and living room, realistic lighting, high detail, minimalist style, "
            f"4k resolution, company style: TERION. Context: {prompt_context}"
        )

        payload = {
            "model": self.model,
            "prompt": reference_prompt,
            "response_format": "b64_json"
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"{self.base_url}/images/generations", headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        img_b64 = data['data'][0]['b64_json']
                        return base64.b64decode(img_b64)
                    else:
                        error_text = await resp.text()
                        print(f"❌ RouterAI Image Error: {resp.status} - {error_text}")
                        return None
            except Exception as e:
                print(f"❌ RouterAI Image Exception: {e}")
                return None

image_gen = ImageGenerator()
