import logging

import openai
from sqlalchemy import select

from app.database import async_session
from app.models.llm_connection import LLMConnection

logger = logging.getLogger(__name__)


async def _get_stt_connection() -> LLMConnection | None:
    async with async_session() as db:
        result = await db.execute(
            select(LLMConnection).where(
                LLMConnection.purpose == "stt",
                LLMConnection.is_default == True,
            )
        )
        conn = result.scalar_one_or_none()
        if conn:
            return conn

        result = await db.execute(
            select(LLMConnection).where(LLMConnection.purpose == "stt").limit(1)
        )
        return result.scalar_one_or_none()


async def transcribe_voice(file_bytes: bytes, filename: str = "voice.ogg") -> str:
    conn = await _get_stt_connection()
    if not conn:
        raise RuntimeError("Нет настроенного STT-подключения. Добавьте подключение в Настройках.")

    logger.info(f"STT call: provider={conn.provider}, model={conn.model}, connection={conn.name}")

    client = openai.AsyncOpenAI(api_key=conn.api_key)
    response = await client.audio.transcriptions.create(
        model=conn.model or "whisper-1",
        file=(filename, file_bytes),
        language="ru",
    )
    return response.text
