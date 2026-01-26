import os
import requests
import json
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "anthropic/claude-3.5-sonnet"

def call_llm(system_prompt, user_message):
    """
    Вызов Claude 3.5 Sonnet через OpenRouter.
    """
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY not found in environment")
        return "Ошибка конфигурации: отсутствует API ключ."

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://lad-v-kvartire.ru", # Optional
        "X-Title": "LAD V KVARTIRE Bot" # Optional
    }

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f"Error calling OpenRouter: {e}")
        return f"Извините, сейчас я испытываю трудности с ответом. Пожалуйста, обратитесь к нашему эксперту Юлии напрямую. {e}"
