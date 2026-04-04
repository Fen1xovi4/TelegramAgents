import json
import logging
import os
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from app.database import async_session
from app.models.agent import Agent
from app.models.video_job import VideoJob
from app.agents.video_shorts.video_utils import (
    job_dir, download_video, extract_audio, find_subtitles,
    parse_vtt, format_transcript_with_timestamps, cut_segment, cleanup_job,
)
from app.agents.video_shorts.prompts import SEGMENT_ANALYSIS_SYSTEM
from app.integrations.anthropic_client import _call_llm
from app.integrations.whisper_client import transcribe_voice

logger = logging.getLogger(__name__)

# Whisper API file size limit
WHISPER_CHUNK_SIZE = 24 * 1024 * 1024  # 24MB to stay under 25MB limit


async def _get_bot_token(agent_id: int) -> str:
    async with async_session() as db:
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one()
        return agent.bot_token


async def _send_message(bot_token: str, chat_id: int, text: str, reply_markup=None):
    bot = Bot(token=bot_token)
    try:
        await bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode="HTML")
    finally:
        await bot.session.close()


async def _send_video(bot_token: str, chat_id: int, video_path: str, caption: str = ""):
    bot = Bot(token=bot_token)
    try:
        video_file = FSInputFile(video_path)
        file_size = os.path.getsize(video_path)

        if file_size > 50 * 1024 * 1024:
            # Over 50MB — send as document
            await bot.send_document(chat_id, video_file, caption=caption)
        else:
            await bot.send_video(chat_id, video_file, caption=caption, supports_streaming=True)
    finally:
        await bot.session.close()


async def _update_job_status(job_id: int, status: str, **kwargs):
    async with async_session() as db:
        result = await db.execute(select(VideoJob).where(VideoJob.id == job_id))
        job = result.scalar_one()
        job.status = status
        for key, value in kwargs.items():
            setattr(job, key, value)
        await db.commit()


def _build_segments_message(segments: list[dict]) -> str:
    """Format segments list for Telegram message."""
    lines = ["🎬 <b>Найденные сегменты:</b>\n"]
    for seg in segments:
        start_m, start_s = divmod(int(seg["start"]), 60)
        end_m, end_s = divmod(int(seg["end"]), 60)
        duration = int(seg["end"] - seg["start"])
        lines.append(
            f"<b>{seg['id']}.</b> «{seg['title']}» "
            f"({start_m}:{start_s:02d} — {end_m}:{end_s:02d}, {duration}с)\n"
            f"   <i>{seg['reason']}</i>\n"
        )
    return "\n".join(lines)


def _build_review_keyboard(job_id: int, segments: list[dict]) -> InlineKeyboardMarkup:
    """Build inline keyboard for segment review."""
    buttons = [
        [InlineKeyboardButton(text="✅ Подтвердить все", callback_data=f"vs:approve:{job_id}")],
    ]
    # Add remove buttons in rows of 3
    remove_btns = []
    for seg in segments:
        remove_btns.append(
            InlineKeyboardButton(text=f"❌ Убрать {seg['id']}", callback_data=f"vs:remove:{job_id}:{seg['id']}")
        )
    for i in range(0, len(remove_btns), 3):
        buttons.append(remove_btns[i:i + 3])

    buttons.append([InlineKeyboardButton(text="🚫 Отмена", callback_data=f"vs:cancel:{job_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def _transcribe_audio_chunks(audio_path: str) -> str:
    """Transcribe audio, chunking if file is too large for Whisper API."""
    file_size = os.path.getsize(audio_path)

    if file_size <= WHISPER_CHUNK_SIZE:
        with open(audio_path, "rb") as f:
            return await transcribe_voice(f.read(), filename="audio.ogg")

    # Split into chunks using ffmpeg
    chunk_duration = 600  # 10 minutes per chunk
    chunks_dir = Path(audio_path).parent / "audio_chunks"
    chunks_dir.mkdir(exist_ok=True)

    import asyncio
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-i", audio_path,
        "-f", "segment", "-segment_time", str(chunk_duration),
        "-c", "copy",
        str(chunks_dir / "chunk_%03d.ogg"),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    # Transcribe each chunk
    transcript_parts = []
    for chunk_path in sorted(chunks_dir.iterdir()):
        if chunk_path.suffix == ".ogg":
            with open(chunk_path, "rb") as f:
                part = await transcribe_voice(f.read(), filename=chunk_path.name)
                transcript_parts.append(part)

    return " ".join(transcript_parts)


# ========================
# ARQ Job Functions
# ========================

async def download_and_analyze(ctx, job_id: int):
    """Main background job: download video, transcribe, analyze, send segments for review."""
    try:
        async with async_session() as db:
            result = await db.execute(select(VideoJob).where(VideoJob.id == job_id))
            job = result.scalar_one()
            youtube_url = job.youtube_url
            chat_id = job.chat_id
            agent_id = job.agent_id

        bot_token = await _get_bot_token(agent_id)
        work_dir = job_dir(job_id)

        # Step 1: Download video
        await _send_message(bot_token, chat_id, "⬇️ Скачиваю видео... (1/3)")
        await _update_job_status(job_id, "downloading")

        video_info = await download_video(youtube_url, work_dir)
        video_path = video_info["filepath"]
        video_title = video_info["title"]
        duration = video_info["duration"]

        await _update_job_status(job_id, "transcribing", video_title=video_title, video_path=video_path)

        # Step 2: Get transcript
        await _send_message(bot_token, chat_id, f"📝 Транскрибирую «{video_title}»... (2/3)")

        # Try subtitles first
        sub_path = find_subtitles(work_dir)
        if sub_path:
            segments = parse_vtt(sub_path)
            transcript = format_transcript_with_timestamps(segments)
            logger.info(f"Job {job_id}: Using downloaded subtitles ({len(segments)} segments)")
        else:
            # Extract audio and transcribe via Whisper
            audio_path = str(work_dir / "audio.ogg")
            await extract_audio(video_path, audio_path)
            raw_transcript = await _transcribe_audio_chunks(audio_path)
            # No timestamps from Whisper API in this mode, create a simple transcript
            transcript = raw_transcript
            logger.info(f"Job {job_id}: Transcribed via Whisper ({len(raw_transcript)} chars)")

        await _update_job_status(job_id, "analyzing", transcript_text=transcript)

        # Step 3: Analyze with LLM
        await _send_message(bot_token, chat_id, "🧠 Анализирую интересные моменты... (3/3)")

        # Get agent config for segment params
        async with async_session() as db:
            result = await db.execute(select(Agent).where(Agent.id == agent_id))
            agent = result.scalar_one()
            config = agent.config or {}

        analysis_prompt = SEGMENT_ANALYSIS_SYSTEM.format(
            title=video_title,
            duration=duration,
            transcript=transcript[:15000],  # Limit transcript size for LLM
            max_segments=config.get("max_segments", 5),
            min_seconds=config.get("min_segment_seconds", 15),
            max_seconds=config.get("max_segment_seconds", 60),
        )

        llm_response = await _call_llm(analysis_prompt, max_tokens=2048)

        # Parse LLM response
        try:
            # Extract JSON from possible markdown code block
            text = llm_response
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            segments_data = json.loads(text)
            if not isinstance(segments_data, list):
                segments_data = []
        except (json.JSONDecodeError, IndexError):
            segments_data = []

        if not segments_data:
            await _update_job_status(job_id, "completed", segments=[])
            await _send_message(
                bot_token, chat_id,
                "🤷 Не удалось найти подходящие моменты для шортсов в этом видео. "
                "Попробуйте другое видео или укажите таймкоды вручную."
            )
            return

        # Ensure segment IDs are sequential
        for i, seg in enumerate(segments_data):
            seg["id"] = i + 1

        await _update_job_status(job_id, "awaiting_review", segments=segments_data)

        # Send segments for review
        msg_text = _build_segments_message(segments_data)
        keyboard = _build_review_keyboard(job_id, segments_data)
        await _send_message(bot_token, chat_id, msg_text, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}", exc_info=True)
        try:
            await _update_job_status(job_id, "failed", error_message=str(e))
            bot_token = await _get_bot_token(
                (await _get_job_agent_id(job_id))
            )
            chat_id = await _get_job_chat_id(job_id)
            await _send_message(bot_token, chat_id, f"❌ Ошибка обработки: {str(e)[:200]}")
        except Exception:
            logger.error(f"Failed to send error message for job {job_id}", exc_info=True)


async def cut_and_send(ctx, job_id: int):
    """Cut video into approved segments and send to user."""
    try:
        async with async_session() as db:
            result = await db.execute(select(VideoJob).where(VideoJob.id == job_id))
            job = result.scalar_one()
            segments = job.approved_segments or job.segments
            video_path = job.video_path
            chat_id = job.chat_id
            agent_id = job.agent_id

        if not segments or not video_path:
            await _update_job_status(job_id, "failed", error_message="No segments or video path")
            return

        bot_token = await _get_bot_token(agent_id)
        work_dir = job_dir(job_id)
        total = len(segments)

        await _update_job_status(job_id, "cutting")
        await _send_message(bot_token, chat_id, f"✂️ Нарезаю {total} шортс(ов)...")

        for i, seg in enumerate(segments, 1):
            output_path = str(work_dir / f"short_{seg['id']}.mp4")

            await cut_segment(video_path, seg["start"], seg["end"], output_path)

            seg_title = seg.get("title", f"Short {seg['id']}")
            caption = f"🎬 {seg_title} ({i}/{total})"
            await _send_video(bot_token, chat_id, output_path, caption=caption)

            await _send_message(bot_token, chat_id, f"✅ Отправлено {i}/{total}")

        await _update_job_status(job_id, "completed")
        await _send_message(bot_token, chat_id, f"🎉 Готово! {total} шортс(ов) отправлено.")

        # Cleanup temp files
        cleanup_job(job_id)

    except Exception as e:
        logger.error(f"Cut job {job_id} failed: {e}", exc_info=True)
        try:
            await _update_job_status(job_id, "failed", error_message=str(e))
            bot_token = await _get_bot_token(agent_id)
            await _send_message(bot_token, chat_id, f"❌ Ошибка нарезки: {str(e)[:200]}")
        except Exception:
            logger.error(f"Failed to send error message for cut job {job_id}", exc_info=True)


async def _get_job_agent_id(job_id: int) -> int:
    async with async_session() as db:
        result = await db.execute(select(VideoJob.agent_id).where(VideoJob.id == job_id))
        return result.scalar_one()


async def _get_job_chat_id(job_id: int) -> int:
    async with async_session() as db:
        result = await db.execute(select(VideoJob.chat_id).where(VideoJob.id == job_id))
        return result.scalar_one()
