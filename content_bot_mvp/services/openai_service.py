import os
import logging
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class OpenAIService:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            self.client = AsyncOpenAI(api_key=api_key)
        else:
            self.client = None
            logger.warning("OPENAI_API_KEY not found. Image generation will be disabled.")

    async def generate_image(self, prompt: str) -> str | None:
        if not self.client:
            return None

        try:
            response = await self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            return response.data[0].url
        except Exception as e:
            logger.error(f"Error generating image with OpenAI: {e}")
            return None

openai_service = OpenAIService()
