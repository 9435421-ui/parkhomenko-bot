<<<<<<< HEAD
import os
import logging
import aiohttp
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class RouterAIClient:
    """RouterAI для текстов и анализа изображений (Gemini/Claude)"""
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ROUTER_API_KEY")
        self.base_url = os.getenv(
            "ROUTER_AI_ENDPOINT", 
            "https://routerai.ru/api/v1/chat/completions"
        ).replace("/chat/completions", "")
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
=======
"""
Router AI — логика ответов в чате (GPT-4 nano / Kimi).
Генерация изображений — отдельно (Nano Banana / OpenRouter), см. services/image_generator.
Яндекс используется для персональных данных и РФ законодательства (fallback в диалоге).
"""
import os
import aiohttp
from typing import Optional, List, Dict


class RouterAIClient:
    """Клиент Router AI: логика ответов (GPT-4 nano / Kimi / Qwen)."""
    
    def __init__(self):
        self.api_key = os.getenv("ROUTER_AI_KEY")
        self.endpoint = os.getenv("ROUTER_AI_ENDPOINT", "https://routerai.ru/api/v1/chat/completions")
        self.default_model = os.getenv("ROUTER_AI_CHAT_MODEL", "gpt-4o-mini")
        self.fallback_model = os.getenv("ROUTER_AI_CHAT_FALLBACK", "qwen")
        self.max_prompt_length = 8000
        
        if not self.api_key:
            print("⚠️ ROUTER_AI_KEY не найден в .env")
    
    async def generate_response(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2000,  # Увеличено до 2000 по умолчанию
        model: Optional[str] = None
    ) -> Optional[str]:
        """
        Генерация ответа через Router AI
        
        Args:
            user_prompt: Запрос пользователя
            system_prompt: Системный промпт
            temperature: Температура генерации
            max_tokens: Максимум токенов
            model: Модель (kimi, qwen, deepseek)
        
        Returns:
            Optional[str]: Ответ от модели или None для переключения на резерв
        """
        if not self.api_key:
            return "⚠️ ROUTER_AI_KEY не настроен. Обратитесь к администратору."
        
        # Проверка длины промпта
        prompt_length = len(user_prompt) + (len(system_prompt) if system_prompt else 0)
        if prompt_length > self.max_prompt_length:
            user_prompt = user_prompt[-4000:]  # Обрезаем если слишком длинный
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        messages.append({
            "role": "user",
            "content": user_prompt
        })
        
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
        }
        
        try:
            async with aiohttp.ClientSession() as session:
<<<<<<< HEAD
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
=======
                async with session.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result["choices"][0]["message"]["content"]
                    else:
                        error_text = await response.text()
                        error_msg = f"Router AI API error {response.status}: {error_text[:500]}"
                        print(f"⚠️ {error_msg}")
                        # Пробуем fallback модель
                        if response.status == 429 and model != self.fallback_model:
                            print("⚠️ Rate limit, пробуем Qwen...")
                            return await self.generate_response(
                                user_prompt=user_prompt,
                                system_prompt=system_prompt,
                                temperature=temperature,
                                max_tokens=max_tokens,
                                model=self.fallback_model
                            )
                        # Пробрасываем ошибку дальше для обработки в вызывающем коде
                        raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Ошибка подключения к Router AI: {str(e)}"
            print(f"⚠️ {error_msg}")
            # Пробрасываем ошибку дальше для обработки в вызывающем коде
            raise Exception(error_msg)
    
    async def generate_with_context(
        self,
        user_query: str,
        rag_context: str,
        dialog_history: Optional[List[Dict[str, str]]] = None,
        user_name: Optional[str] = None,
        consultant_style: bool = True
    ) -> Optional[str]:
        """
        Генерация ответа консультанта с контекстом
        
        Args:
            user_query: Вопрос пользователя
            rag_context: Контекст из базы знаний
            dialog_history: История диалога
            user_name: Имя пользователя
            consultant_style: Использовать стиль Антона
        
        Returns:
            Optional[str]: Ответ консультанта или None для переключения на резерв
        """
        if consultant_style:
            system_prompt = self._build_anton_system_prompt()
        else:
            system_prompt = ""
        
        # Формируем историю
        history_text = ""
        if dialog_history and len(dialog_history) > 1:
            recent = dialog_history[-6:-1]
            history_parts = []
            for h in recent:
                name = "Клиент" if h['role'] == 'user' else "Антон"
                history_parts.append(f"{name}: {h['text']}")
            history_text = "\n".join(history_parts)
        
        # Формируем историю для промпта (совместимость с Python 3.11)
        history_prefix = "ИСТОРИЯ ДИАЛОГА:\n" + history_text + "\n" if history_text else ""
        
        user_prompt = rag_context + "\n\n" + history_prefix + "---\n" + "НОВЫЙ ВОПРОС КЛИЕНТА: " + user_query + "\n\nОтвечай кратко (2-3 предложения), по делу, со ссылками на законы из контекста."
        
        return await self.generate_response(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=400
        )
    
    def _build_anton_system_prompt(self) -> str:
        """
        Системный промпт для ИИ-консультанта Антона (Терион)
        """
        return """
Ты — Антон, ИИ-консультант компании Терион по перепланировкам и согласованиям.

СТИЛЬ И ТОН:
- Профессиональный, но дружелюбный
- Говори "наша команда", "специалисты Териона"
- Всегда добавляй в конце: "Точную информацию по вашему объекту даст эксперт Терион после анализа документов."

ПРАВИЛА ОТВЕТОВ:
1. Лимит: 250-350 символов (2-3 предложения)
2. НЕ повторяй информацию из истории диалога
3. НЕ называй конкретные суммы и сроки
4. НЕ давай гарантий 100% результата
5. Ссылайся на законы: "Согласно ст. 26 ЖК РФ...", "По п. 508-ПП Москвы..."
6. НЕ предполагай город — спрашивай если не назван
7. После 2-3 ответов предлагай оставить заявку

ЕСЛИ НЕТ ОТВЕТА В КОНТЕКСТЕ:
"К сожалению, в базе знаний нет точной информации по этому вопросу. 
Рекомендую записаться на консультацию к эксперту Терион для детального разбора вашей ситуации."

ТЫ НЕ МОЖЕШЬ:
- Давать инструкции по строительным работам
- Обещать конкретные сроки согласования
- Заменять консультацию эксперта
""".strip()


# Singleton
router_ai = RouterAIClient()

# Alias для совместимости
async def generate(system_prompt: str = "", user_message: str = "", max_tokens: int = 2000) -> Optional[str]:
    """Удобная функция-алиас для generate_response"""
    return await router_ai.generate_response(
        user_prompt=user_message or system_prompt,
        system_prompt=system_prompt if system_prompt else None,
        max_tokens=max_tokens
    )
>>>>>>> 7088a20d30a8942893a1c5c26400c6546150a377
