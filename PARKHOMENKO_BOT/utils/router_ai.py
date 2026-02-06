from openai import AsyncOpenAI
import os
from config import ROUTER_AI_KEY

class RouterAIClient:
    def __init__(self):
        self.api_key = ROUTER_AI_KEY
        self.base_url = "https://routerai.ru/api/v1"
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        self.text_model = "qwen-2.5-max"

    async def improve_text(self, text: str) -> str:
        """Улучшение текста для постов компании ТЕРИОН (qwen-2.5-max)"""
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
        try:
            response = await self.client.chat.completions.create(
                model=self.text_model,
                messages=[
                    {"role": "system", "content": "Ты ИИ-ассистент компании ТЕРИОН."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"❌ Ошибка RouterAI: {str(e)}"

router_ai = RouterAIClient()
