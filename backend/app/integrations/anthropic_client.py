import json
import logging

import anthropic
import openai
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.llm_connection import LLMConnection

logger = logging.getLogger(__name__)


async def _get_default_connection(purpose: str) -> LLMConnection | None:
    """Get the default LLM connection for given purpose from DB."""
    async with async_session() as db:
        # Try default first
        result = await db.execute(
            select(LLMConnection).where(
                LLMConnection.purpose == purpose,
                LLMConnection.is_default == True,
            )
        )
        conn = result.scalar_one_or_none()
        if conn:
            return conn

        # Fallback: any connection for this purpose
        result = await db.execute(
            select(LLMConnection).where(LLMConnection.purpose == purpose).limit(1)
        )
        return result.scalar_one_or_none()


async def _call_openai_chat(api_key: str, model: str, messages: list[dict], max_tokens: int) -> str:
    client = openai.AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
    )
    return response.choices[0].message.content.strip()


async def _call_anthropic_chat(api_key: str, model: str, messages: list[dict], max_tokens: int) -> str:
    client = anthropic.AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=messages,
    )
    return response.content[0].text.strip()


async def _call_llm(prompt: str, max_tokens: int = 256) -> str:
    conn = await _get_default_connection("chat")
    if not conn:
        raise RuntimeError("Нет настроенного LLM-подключения для чата. Добавьте подключение в Настройках.")

    messages = [{"role": "user", "content": prompt}]
    logger.info(f"LLM call: provider={conn.provider}, model={conn.model}, connection={conn.name}")

    if conn.provider == "openai":
        return await _call_openai_chat(conn.api_key, conn.model, messages, max_tokens)
    elif conn.provider == "anthropic":
        return await _call_anthropic_chat(conn.api_key, conn.model, messages, max_tokens)
    else:
        raise RuntimeError(f"Неизвестный провайдер: {conn.provider}")


async def parse_intent(prompt: str) -> dict:
    text = await _call_llm(prompt, max_tokens=256)
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            return {"intent": "unknown", "params": {}}
        return data
    except (json.JSONDecodeError, IndexError):
        return {"intent": "unknown", "params": {}}


async def generate_response(prompt: str) -> str:
    return await _call_llm(prompt, max_tokens=1024)
