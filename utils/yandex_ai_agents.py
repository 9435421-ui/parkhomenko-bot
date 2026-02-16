"""
Умный Охотник v2.0: вызов агентов Yandex AI Studio.
Агент-Шпион (fvt2vnpq2qjdt829em50): анализ сообщений из чатов, нормативная база → JSON (hotness, recommendation).
Агент-Антон (fvtrdfvmv1u84s9rfn5a): ответ с Retrieval (база знаний), до 500 знаков, дисклеймер, призыв квиза.
При отсутствии YANDEX_AI_AGENTS_ENDPOINT используется fallback на Router AI / YandexGPT с промптами.
"""
import os
import re
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


async def call_spy_agent(message_text: str) -> Dict[str, Any]:
    """
    Агент-Шпион: анализ сообщения из чата ЖК. Ожидается JSON с hotness (1-5), recommendation (вердикт), pain_level.
    """
    endpoint = os.getenv("YANDEX_AI_AGENTS_ENDPOINT")
    agent_id = os.getenv("YANDEX_AI_AGENT_SPY_ID", "fvt2vnpq2qjdt829em50")
    if endpoint and agent_id:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    json={"agent_id": agent_id, "message": message_text[:4000]},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        text = data.get("output", data.get("response", data.get("text", "")))
                        if isinstance(text, str):
                            return _parse_spy_json(text)
                        return data if isinstance(data, dict) else {"hotness": 3, "recommendation": ""}
        except Exception as e:
            logger.warning("Yandex AI Agent (Spy) request failed: %s", e)

    # Fallback: Router AI с запросом JSON
    try:
        from utils.router_ai import router_ai
        prompt = (
            f"Сообщение из чата ЖК: «{message_text[:1500]}»\n\n"
            "Проанализируй как лид (запрос на перепланировку/согласование). "
            "Верни только валидный JSON без markdown, в одну строку: "
            '{"hotness": число 1-5, "recommendation": "вердикт/действие одним предложением", "pain_level": число 1-5}'
        )
        response = await router_ai.generate_response(prompt, model="kimi")
        if response:
            return _parse_spy_json(response)
    except Exception as e:
        logger.warning("Spy fallback (Router AI) failed: %s", e)

    return {"hotness": 3, "recommendation": "", "pain_level": 3}


def _parse_spy_json(text: str) -> Dict[str, Any]:
    try:
        cleaned = re.sub(r"^[^{]*", "", text)
        cleaned = re.sub(r"[^}]*$", "", cleaned)
        obj = json.loads(cleaned)
        return {
            "hotness": int(obj.get("hotness", 3)) if obj.get("hotness") is not None else 3,
            "recommendation": str(obj.get("recommendation", "") or obj.get("verdict", "")),
            "pain_level": int(obj.get("pain_level", 3)) if obj.get("pain_level") is not None else 3,
        }
    except Exception:
        return {"hotness": 3, "recommendation": "", "pain_level": 3}


async def call_anton_agent(context: str, max_chars: int = 500) -> str:
    """
    Агент-Антон: экспертный ответ по контексту (сообщение лида), с учётом базы знаний (Retrieval).
    Ограничение по длине, затем добавляются дисклеймер и призыв пройти квиз.
    """
    endpoint = os.getenv("YANDEX_AI_AGENTS_ENDPOINT")
    agent_id = os.getenv("YANDEX_AI_AGENT_ANTON_ID", "fvtrdfvmv1u84s9rfn5a")
    if endpoint and agent_id:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    json={"agent_id": agent_id, "message": context[:3000]},
                    timeout=aiohttp.ClientTimeout(total=45),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        text = data.get("output", data.get("response", data.get("text", "")))
                        if isinstance(text, str):
                            return _truncate_and_append_anton(text, max_chars)
        except Exception as e:
            logger.warning("Yandex AI Agent (Anton) request failed: %s", e)

    # Fallback: RAG через router_ai
    try:
        from utils import router_ai, kb
        rag = await kb.get_context(context[:1000], max_chunks=3, context_size=600)
        reply = await router_ai.generate_with_context(
            user_query=context[:800],
            rag_context=rag,
            dialog_history=None,
            consultant_style=True,
        )
        if reply:
            return _truncate_and_append_anton(reply, max_chars)
    except Exception as e:
        logger.warning("Anton fallback (RAG) failed: %s", e)

    return _truncate_and_append_anton(
        "Рекомендую уточнить детали объекта и прислать план. Мы поможем с оценкой по нормативам.",
        max_chars,
    )


def _truncate_and_append_anton(text: str, max_chars: int = 500) -> str:
    """Обрезать до max_chars, добавить дисклеймер и призыв квиза."""
    disclaimer = "\n\nС уважением, Антон — ИИ-помощник эксперта Юлии Пархоменко."
    cta = "\n\nПройти квиз для заявки: @Parkhovenko_i_kompaniya_bot"
    budget = max_chars - len(disclaimer) - len(cta)
    body = (text or "").strip()[:budget]
    if len((text or "").strip()) > budget:
        body = body.rstrip()
        if not body.endswith(".") and not body.endswith("!"):
            body += "..."
    return body + disclaimer + cta


async def call_anton_quiz_summary(quiz_summary: str) -> str:
    """Предварительное заключение эксперта по сводке ответов квиза (база знаний / Retrieval)."""
    endpoint = os.getenv("YANDEX_AI_AGENTS_ENDPOINT")
    agent_id = os.getenv("YANDEX_AI_AGENT_ANTON_ID", "fvtrdfvmv1u84s9rfn5a")
    if endpoint and agent_id:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    json={
                        "agent_id": agent_id,
                        "message": f"Сводка ответов клиента по квизу:\n{quiz_summary[:3000]}\n\nСформируй предварительное заключение эксперта Юлии Пархоменко на основе базы знаний (до 600 знаков).",
                    },
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return (data.get("output") or data.get("response") or data.get("text") or "")[:800]
        except Exception as e:
            logger.warning("Anton quiz summary (Agent API) failed: %s", e)

    try:
        from utils import router_ai, kb
        rag = await kb.get_context(quiz_summary[:1500], max_chunks=5, context_size=1000)
        reply = await router_ai.generate_response(
            f"По ответам клиента из квиза сформируй краткое предварительное заключение (до 500 знаков), опираясь на контекст:\n{rag}\n\nСводка ответов:\n{quiz_summary[:1500]}",
            max_tokens=400,
        )
        return (reply or "")[:800]
    except Exception as e:
        logger.warning("Anton quiz summary fallback failed: %s", e)
    return "Предварительное заключение будет подготовлено экспертом после изучения заявки."
