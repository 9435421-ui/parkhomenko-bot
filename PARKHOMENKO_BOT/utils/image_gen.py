from openai import AsyncOpenAI
import os
import base64
from config import ROUTER_AI_KEY

class ImageGenerator:
    def __init__(self):
        self.api_key = ROUTER_AI_KEY
        self.base_url = "https://routerai.ru/api/v1"
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        self.model = "flux-1-dev"

    async def generate_image(self, prompt_context: str) -> bytes:
        """Генерация изображения через RouterAI (flux-1-dev)"""
        # Эталонный промпт из ТЗ v2.6/v2.7
        reference_prompt = (
            "Professional architectural 3D visualization of a modern apartment renovation, "
            "open space kitchen and living room, realistic lighting, high detail, minimalist style, "
            f"4k resolution, company style: TERION. Context: {prompt_context}"
        )

        try:
            response = await self.client.images.generate(
                model=self.model,
                prompt=reference_prompt,
                response_format="b64_json"
            )
            img_b64 = response.data[0].b64_json
            return base64.b64decode(img_b64)
        except Exception as e:
            print(f"❌ RouterAI Image Exception: {e}")
            return None

image_gen = ImageGenerator()
