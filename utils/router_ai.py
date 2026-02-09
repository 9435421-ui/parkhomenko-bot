"""
Интеграция с Router AI для Kimi/Qwen (основной LLM для ответов)
"""
import os
import aiohttp
from typing import Optional, List, Dict


class RouterAIClient:
    """Клиент для работы с Router AI (Kimi, Qwen, DeepSeek и др.)"""
    
    def __init__(self):
        self.api_key = os.getenv("ROUTER_AI_KEY")
        self.endpoint = "https://router.huge.ai/api/chat/completions"
        self.default_model = "kimi"
        self.fallback_model = "qwen"
        self.max_prompt_length = 8000
        
        if not self.api_key:
            print("⚠️ ROUTER_AI_KEY не найден в .env")
    
    async def generate_response(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 500,
        model: Optional[str] = None
    ) -> str:
        """
        Генерация ответа через Router AI
        
        Args:
            user_prompt: Запрос пользователя
            system_prompt: Системный промпт
            temperature: Температура генерации
            max_tokens: Максимум токенов
            model: Модель (kimi, qwen, deepseek)
        
        Returns:
            str: Ответ от модели
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
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=90)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result["choices"][0]["message"]["content"]
                    else:
                        error_text = await response.text()
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
                        return f"Ошибка Router AI: {response.status}"
        except Exception as e:
            return f"Ошибка подключения к Router AI: {str(e)}"
    
    async def generate_with_context(
        self,
        user_query: str,
        rag_context: str,
        dialog_history: Optional[List[Dict[str, str]]] = None,
        user_name: Optional[str] = None,
        consultant_style: bool = True
    ) -> str:
        """
        Генерация ответа консультанта с контекстом
        
        Args:
            user_query: Вопрос пользователя
            rag_context: Контекст из базы знаний
            dialog_history: История диалога
            user_name: Имя пользователя
            consultant_style: Использовать стиль Антона
        
        Returns:
            str: Ответ консультанта
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
        
        # Формируем историю для промпта
        history_block = ""
        if history_text:
            history_block = f"ИСТОРИЯ ДИАЛОГА:\n{history_text}\n"
        
        user_prompt = f"""
{rag_context}

{history_block}
---
НОВЫЙ ВОПРОС КЛИЕНТА: {user_query}

Отвечай кратко (2-3 предложения), по делу, со ссылками на законы из контекста.
"""
        
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
async def generate(system_prompt: str, user_message: str, max_tokens: int = 500) -> Optional[str]:
    """Удобная функция-алиас для generate_response"""
    return await router_ai.generate_response(
        user_prompt=user_message,
        system_prompt=system_prompt,
        max_tokens=max_tokens
    )
