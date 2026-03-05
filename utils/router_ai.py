import os
import logging
import aiohttp
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class RouterAIClient:
    """RouterAI для текстов и анализа изображений (Gemini/Claude)"""
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ROUTER_API_KEY")
        self.base_url = "https://router.ai/api/v1" # Уточнить URL при необходимости
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def generate(
        self, 
        prompt: str, 
        system_prompt: str = "Ты — Антон, ИИ-эксперт по перепланировкам.",
        model: str = "gemini-1.5-flash",
        temperature: float = 0.7
    ) -> Optional[str]:
        """Генерация текста."""
        if not self.api_key:
            logger.warning("ROUTER_API_KEY не настроен")
            return None
            
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data['choices'][0]['message']['content']
                    else:
                        logger.error(f"RouterAI error {resp.status}: {await resp.text()}")
            return None
        except Exception as e:
            logger.error(f"RouterAI exception: {e}")
            return None

    async def analyze_image(self, image_b64: str, prompt: str) -> Optional[str]:
        """Анализ изображения через Gemini 1.5 Flash (Vision)"""
        if not self.api_key: return None
        
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": "gemini-1.5-flash",
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
                ]
            }],
            "max_tokens": 2000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=self.headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data['choices'][0]['message']['content']
            return None
        except Exception as e:
            logger.error(f"RouterAI Vision exception: {e}")
            return None

# Singleton
router_ai = RouterAIClient()
