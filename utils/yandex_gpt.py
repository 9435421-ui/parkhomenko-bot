"""
Интеграция с YandexGPT API
"""
import os
import aiohttp
from typing import Optional, List, Dict


class YandexGPTClient:
    """Клиент для работы с YandexGPT API"""
    
    def __init__(self):
        self.api_key = os.getenv("YANDEX_API_KEY")
        self.folder_id = os.getenv("FOLDER_ID")
        self.endpoint = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        self.max_prompt_length = 3000  # Максимальная длина промпта в символах
        
        if not self.api_key or not self.folder_id:
            raise ValueError("YANDEX_API_KEY and FOLDER_ID must be set in environment")
    
    async def generate_response(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 400,
        model: str = "yandexgpt"
    ) -> str:
        """
        Генерация ответа от YandexGPT
        
        Args:
            user_prompt: Запрос пользователя
            system_prompt: Системный промпт (опционально)
            temperature: Температура генерации (0.0-1.0)
            max_tokens: Максимальное количество токенов
            model: Модель (yandexgpt или yandexgpt-lite)
        
        Returns:
            str: Ответ от модели
        """
        # Проверка длины промпта
        prompt_length = len(user_prompt) + (len(system_prompt) if system_prompt else 0)
        if prompt_length > self.max_prompt_length:
            print(f"⚠️ ОШИБКА: Длина промпта ({prompt_length} символов) превышает лимит ({self.max_prompt_length} символов)")
            print(f"⚠️ Запрос не будет отправлен для экономии средств")
            return "Извините, запрос слишком большой. Пожалуйста, сформулируйте вопрос короче."
        
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }
        
        messages = []
        
        if system_prompt:
            messages.append({
                "role": "system",
                "text": system_prompt
            })
        
        messages.append({
            "role": "user",
            "text": user_prompt
        })
        
        payload = {
            "modelUri": f"gpt://{self.folder_id}/{model}/latest",
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": max_tokens
            },
            "messages": messages
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result["result"]["alternatives"][0]["message"]["text"]
                    else:
                        error_text = await response.text()
                        return f"Ошибка API YandexGPT: {response.status} - {error_text}"
        except Exception as e:
            return f"Ошибка подключения к YandexGPT: {str(e)}"
    
    async def generate_with_context(
        self,
        user_query: str,
        rag_context: str,
        dialog_history: Optional[List[Dict[str, str]]] = None,
        user_name: Optional[str] = None
    ) -> str:
        """
        Генерация ответа с учётом контекста из RAG и истории диалога
        
        Args:
            user_query: Вопрос пользователя
            rag_context: Контекст из базы знаний
            dialog_history: История диалога
            user_name: Имя пользователя для персонализации
        
        Returns:
            str: Ответ консультанта
        """
        system_prompt = self._build_consultant_system_prompt()
        
        # Формируем историю диалога
        history_text = ""
        if dialog_history and len(dialog_history) > 1:
            recent_history = dialog_history[-6:-1]  # Последние 5 сообщений
            history_text = "\n".join([
                f"{'Клиент' if h['role'] == 'user' else 'Консультант'}: {h['text']}"
                for h in recent_history
            ])
        
        # Формируем полный промпт
        user_prompt = f"""
{system_prompt}

================ КОНТЕКСТ ИЗ БАЗЫ ЗНАНИЙ ================
{rag_context}

{f"ИСТОРИЯ ДИАЛОГА (ЧТО УЖЕ БЫЛО СКАЗАНО):\n{history_text}\n" if history_text else ""}

НОВЫЙ ВОПРОС КЛИЕНТА:
{user_query}

ТВОЯ ЗАДАЧА:
1. Прочитай ИСТОРИЮ — что клиент УЖЕ сказал (город, этаж, тип дома)
2. НЕ повторяй информацию, которую УЖЕ давал
3. Дай ТОЛЬКО новую полезную информацию из КОНТЕКСТА (250-350 символов)
4. Каждое сообщение должно ПРОДВИГАТЬ диалог вперёд
"""
        
        greeting = f"{user_name}, " if user_name else ""
        
        return await self.generate_response(
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=400
        )
    
    def _build_consultant_system_prompt(self) -> str:
        """Формирует системный промпт для ИИ-консультанта"""
        return """
Ты — ИИ-помощник нашего эксперта по согласованию перепланировок (Москва/МО, 10+ лет опыта).

ЖЕЛЕЗНЫЕ ПРАВИЛА:
1. Читай историю — НЕ задавай вопросы, на которые клиент УЖЕ ответил
2. НЕ повторяй информацию, которую УЖЕ озвучил
3. Каждый ответ — ТОЛЬКО новая информация
4. Лимит: 250-350 символов (2-3 предложения max)
5. УПОМИНАЙ КОМПАНИЮ: в каждом 2-3 ответе говори "наша команда", "ТЕРИОН"
6. НЕ ПРЕДПОЛАГАЙ ГОРОД: НЕ говори "в Москве" пока клиент не назвал город
7. КОГДА КЛИЕНТ ХОЧЕТ ОБСУДИТЬ ДЕТАЛИ:
   - Задай 2-3 конкретных вопроса про объект (тип дома, документы БТИ, коммуникации)
   - Дай 2-3 совета из базы знаний
   - Только ПОТОМ мягко предложи заявку
8. СТОИМОСТЬ:
   - НИКОГДА не называй конкретные суммы
   - Объясни, что цена зависит от объекта, объёма работ и документов
   - Предложи обсудить стоимость со специалистом
9. ВОПРОСЫ НА ЧЕЛОВЕЧЕСКОМ ЯЗЫКЕ:
   - Задавай вопросы простым языком
   - Не используй технические термины без объяснения
   - Максимум 2-3 вопроса в одном ответе

НЕ ДЕЛАЙ НИКОГДА:
× Не повторяй уже сказанное
× НЕ называй конкретные цены и суммы
× НЕ говори "в Москве" пока клиент не назвал город
× НЕ предлагай заявку сразу — сначала задай вопросы и дай советы
""".strip()


# Singleton instance
yandex_gpt = YandexGPTClient()
