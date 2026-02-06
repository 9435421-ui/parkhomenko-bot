import aiohttp
import json
from config import ROUTER_AI_KEY

class RouterAIClient:
    def __init__(self):
        self.api_key = ROUTER_AI_KEY
        self.base_url = "https://routerai.ru/api/v1"
        self.text_model = "deepseek-v3"

    async def improve_text(self, text: str) -> str:
        """Улучшение текста для постов компании ТЕРИОН (deepseek-v3)"""
        prompt = (
            "Ты — эксперт по перепланировкам компании ТЕРИОН. "
            "Преврати краткий комментарий или факты в продающий, профессиональный и структурированный пост для соцсетей. "
            "Добавь хэштеги #терион #перепланировка #дизайн. "
            f"\n\nТекст:\n{text}"
        )
        return await self._generate(prompt)

    async def get_answer(self, query: str) -> str:
        """Гибкий ответ по теме перепланировок"""
        prompt = (
            "Ты — эксперт по перепланировкам ТЕРИОН. Ответь на вопрос клиента максимально подробно и грамотно. "
            "Если вопрос не касается перепланировок, вежливо направь клиента к теме услуг ТЕРИОН. "
            f"\n\nВопрос:\n{query}"
        )
        return await self._generate(prompt)

    async def _generate(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.text_model,
            "messages": [
                {"role": "system", "content": "Ты ИИ-ассистент компании ТЕРИОН."},
                {"role": "user", "content": prompt}
            ]
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"{self.base_url}/chat/completions", headers=headers, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data['choices'][0]['message']['content']
                    else:
                        error_text = await resp.text()
                        return f"❌ Ошибка RouterAI ({resp.status}): {error_text}"
            except Exception as e:
                return f"❌ Ошибка RouterAI: {str(e)}"

router_ai = RouterAIClient()
