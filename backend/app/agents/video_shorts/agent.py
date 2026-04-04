import re
import logging

from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentMessage, AgentResponse, BaseAgent
from app.agents.registry import AgentRegistry
from app.agents.video_shorts.prompts import INTENT_PARSE_SYSTEM
from app.agents.video_shorts.jobs import (
    _build_segments_message, _build_review_keyboard, _update_job_status,
)
from app.agents.video_shorts.video_utils import get_video_info, cleanup_job
from app.config import settings
from app.integrations.anthropic_client import parse_intent
from app.models.video_job import VideoJob

logger = logging.getLogger(__name__)

YOUTUBE_URL_REGEX = re.compile(
    r"(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)[\w\-]+"
)


def _extract_youtube_url(text: str) -> str | None:
    match = YOUTUBE_URL_REGEX.search(text)
    return match.group(0) if match else None


async def _enqueue_job(function_name: str, **kwargs):
    redis = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
    await redis.enqueue_job(function_name, **kwargs)
    await redis.close()


@AgentRegistry.register
class VideoShortsAgent(BaseAgent):
    agent_type = "video_shorts"

    _user_state: dict[int, str] = {}

    def get_default_config(self) -> dict:
        return {
            "welcome_message": (
                "🎬 Отправьте мне ссылку на YouTube видео, и я найду самые "
                "интересные моменты для шортсов!\n\n"
                "Я скачаю видео, проанализирую и предложу сегменты для нарезки."
            ),
            "max_video_duration_minutes": 30,
            "max_segments": 5,
            "min_segment_seconds": 15,
            "max_segment_seconds": 60,
            "video_quality": "720p",
            "language": "ru",
        }

    def get_roles(self) -> list[str]:
        return ["admin", "user"]

    async def handle_message(self, message: AgentMessage, db: AsyncSession) -> AgentResponse:
        # Quick check: is this a YouTube URL?
        url = _extract_youtube_url(message.text)
        if url:
            return await self._handle_submit_video(url, message, db)

        # LLM intent parsing
        intent_data = await parse_intent(
            INTENT_PARSE_SYSTEM.format(text=message.text)
        )
        intent = intent_data.get("intent", "unknown")
        params = intent_data.get("params", {})

        match intent:
            case "greeting":
                return AgentResponse(
                    text=message.agent_config.get("welcome_message", self.get_default_config()["welcome_message"]),
                    intent=intent,
                )
            case "help":
                return AgentResponse(text=self._help_text(), intent=intent)
            case "submit_video":
                video_url = params.get("url") or _extract_youtube_url(message.text)
                if video_url:
                    return await self._handle_submit_video(video_url, message, db)
                return AgentResponse(text="Отправьте ссылку на YouTube видео.", intent=intent)
            case "confirm_segments":
                return await self._handle_confirm(message, db)
            case "edit_segment":
                return await self._handle_edit_segment(params, message, db)
            case "remove_segment":
                return await self._handle_remove_segment(params, message, db)
            case "check_status":
                return await self._handle_status(message, db)
            case "cancel":
                return await self._handle_cancel(message, db)
            case _:
                return AgentResponse(
                    text="Не совсем понял. Отправьте ссылку на YouTube видео или напишите /help.",
                    intent="unknown",
                )

    async def handle_callback_query(
        self, callback_data: str, telegram_id: int, chat_id: int, agent_id: int, db: AsyncSession
    ) -> str | None:
        """Handle inline button callbacks for segment review."""
        parts = callback_data.split(":")
        if len(parts) < 3 or parts[0] != "vs":
            return None

        action = parts[1]
        job_id = int(parts[2])

        # Verify job belongs to this user and agent
        result = await db.execute(
            select(VideoJob).where(
                VideoJob.id == job_id,
                VideoJob.agent_id == agent_id,
                VideoJob.telegram_id == telegram_id,
            )
        )
        job = result.scalar_one_or_none()
        if not job:
            return "Задание не найдено."

        if action == "approve":
            if job.status != "awaiting_review":
                return "Задание уже обработано."
            job.approved_segments = job.segments
            await db.commit()
            await _enqueue_job("cut_and_send", job_id=job_id)
            return "✅ Сегменты подтверждены! Начинаю нарезку..."

        elif action == "remove" and len(parts) == 4:
            if job.status != "awaiting_review":
                return "Задание уже обработано."
            seg_id = int(parts[3])
            segments = [s for s in (job.segments or []) if s["id"] != seg_id]

            if not segments:
                job.status = "cancelled"
                await db.commit()
                cleanup_job(job_id)
                return "Все сегменты удалены. Задание отменено."

            # Re-number
            for i, seg in enumerate(segments):
                seg["id"] = i + 1
            job.segments = segments
            await db.commit()

            # Send updated segments via bot
            from app.agents.video_shorts.jobs import _get_bot_token, _send_message
            bot_token = await _get_bot_token(agent_id)
            msg_text = _build_segments_message(segments)
            keyboard = _build_review_keyboard(job_id, segments)
            await _send_message(bot_token, chat_id, msg_text, reply_markup=keyboard)

            return f"Сегмент {seg_id} удалён."

        elif action == "cancel":
            job.status = "cancelled"
            await db.commit()
            cleanup_job(job_id)

            from app.agents.video_shorts.jobs import _get_bot_token, _send_message
            bot_token = await _get_bot_token(agent_id)
            await _send_message(bot_token, chat_id, "🚫 Обработка отменена.")

            return "Отменено."

        return None

    async def _handle_submit_video(
        self, url: str, message: AgentMessage, db: AsyncSession
    ) -> AgentResponse:
        # Check for active job
        result = await db.execute(
            select(VideoJob).where(
                VideoJob.agent_id == message.agent_id,
                VideoJob.telegram_id == message.telegram_id,
                VideoJob.status.notin_(["completed", "failed", "cancelled"]),
            )
        )
        active_job = result.scalar_one_or_none()
        if active_job:
            return AgentResponse(
                text=f"⏳ У вас уже есть активное задание (#{active_job.id}). "
                     f"Дождитесь завершения или отмените его командой «отмена».",
                intent="submit_video",
            )

        # Validate video
        try:
            info = await get_video_info(url)
        except Exception as e:
            return AgentResponse(
                text=f"❌ Не удалось получить информацию о видео: {str(e)[:200]}",
                intent="submit_video",
            )

        duration = info.get("duration", 0)
        max_duration = message.agent_config.get("max_video_duration_minutes", 30) * 60

        if duration > max_duration:
            return AgentResponse(
                text=f"❌ Видео слишком длинное ({duration // 60} мин). "
                     f"Максимум: {max_duration // 60} мин.",
                intent="submit_video",
            )

        title = info.get("title", "Unknown")

        # Create job
        video_job = VideoJob(
            agent_id=message.agent_id,
            telegram_id=message.telegram_id,
            chat_id=message.chat_id,
            youtube_url=url,
            video_title=title,
            status="downloading",
        )
        db.add(video_job)
        await db.commit()
        await db.refresh(video_job)

        # Enqueue background job
        await _enqueue_job("download_and_analyze", job_id=video_job.id)

        return AgentResponse(
            text=f"🎬 Принято! «{title}» ({duration // 60}:{duration % 60:02d})\n"
                 f"Начинаю обработку. Это может занять 2-5 минут.",
            intent="submit_video",
            intent_data={"url": url, "title": title, "job_id": video_job.id},
        )

    async def _handle_confirm(self, message: AgentMessage, db: AsyncSession) -> AgentResponse:
        result = await db.execute(
            select(VideoJob).where(
                VideoJob.agent_id == message.agent_id,
                VideoJob.telegram_id == message.telegram_id,
                VideoJob.status == "awaiting_review",
            )
        )
        job = result.scalar_one_or_none()
        if not job:
            return AgentResponse(text="Нет заданий, ожидающих подтверждения.", intent="confirm_segments")

        job.approved_segments = job.segments
        await db.commit()

        await _enqueue_job("cut_and_send", job_id=job.id)

        return AgentResponse(
            text="✅ Сегменты подтверждены! Начинаю нарезку...",
            intent="confirm_segments",
        )

    async def _handle_edit_segment(
        self, params: dict, message: AgentMessage, db: AsyncSession
    ) -> AgentResponse:
        result = await db.execute(
            select(VideoJob).where(
                VideoJob.agent_id == message.agent_id,
                VideoJob.telegram_id == message.telegram_id,
                VideoJob.status == "awaiting_review",
            )
        )
        job = result.scalar_one_or_none()
        if not job:
            return AgentResponse(text="Нет заданий для редактирования.", intent="edit_segment")

        seg_id = params.get("segment_id")
        if not seg_id:
            return AgentResponse(text="Укажите номер сегмента.", intent="edit_segment")

        segments = job.segments or []
        seg = next((s for s in segments if s["id"] == int(seg_id)), None)
        if not seg:
            return AgentResponse(text=f"Сегмент {seg_id} не найден.", intent="edit_segment")

        if start := params.get("start"):
            seg["start"] = float(start)
        if end := params.get("end"):
            seg["end"] = float(end)

        job.segments = segments
        await db.commit()

        return AgentResponse(
            text=f"✏️ Сегмент {seg_id} обновлён: {seg['start']:.0f}с — {seg['end']:.0f}с",
            intent="edit_segment",
        )

    async def _handle_remove_segment(
        self, params: dict, message: AgentMessage, db: AsyncSession
    ) -> AgentResponse:
        result = await db.execute(
            select(VideoJob).where(
                VideoJob.agent_id == message.agent_id,
                VideoJob.telegram_id == message.telegram_id,
                VideoJob.status == "awaiting_review",
            )
        )
        job = result.scalar_one_or_none()
        if not job:
            return AgentResponse(text="Нет заданий для редактирования.", intent="remove_segment")

        seg_id = params.get("segment_id")
        if not seg_id:
            return AgentResponse(text="Укажите номер сегмента.", intent="remove_segment")

        segments = [s for s in (job.segments or []) if s["id"] != int(seg_id)]
        if not segments:
            job.status = "cancelled"
            await db.commit()
            cleanup_job(job.id)
            return AgentResponse(text="Все сегменты удалены. Задание отменено.", intent="remove_segment")

        for i, seg in enumerate(segments):
            seg["id"] = i + 1
        job.segments = segments
        await db.commit()

        return AgentResponse(
            text=f"❌ Сегмент {seg_id} удалён. Осталось: {len(segments)}",
            intent="remove_segment",
        )

    async def _handle_status(self, message: AgentMessage, db: AsyncSession) -> AgentResponse:
        result = await db.execute(
            select(VideoJob).where(
                VideoJob.agent_id == message.agent_id,
                VideoJob.telegram_id == message.telegram_id,
                VideoJob.status.notin_(["completed", "failed", "cancelled"]),
            )
        )
        job = result.scalar_one_or_none()
        if not job:
            return AgentResponse(text="У вас нет активных заданий.", intent="check_status")

        status_map = {
            "downloading": "⬇️ Скачивание видео...",
            "transcribing": "📝 Транскрипция...",
            "analyzing": "🧠 Анализ...",
            "awaiting_review": "⏳ Ожидание подтверждения сегментов",
            "cutting": "✂️ Нарезка шортсов...",
            "sending": "📤 Отправка...",
        }
        status_text = status_map.get(job.status, job.status)

        return AgentResponse(
            text=f"Задание #{job.id}: {status_text}\nВидео: {job.video_title or job.youtube_url}",
            intent="check_status",
        )

    async def _handle_cancel(self, message: AgentMessage, db: AsyncSession) -> AgentResponse:
        result = await db.execute(
            select(VideoJob).where(
                VideoJob.agent_id == message.agent_id,
                VideoJob.telegram_id == message.telegram_id,
                VideoJob.status.notin_(["completed", "failed", "cancelled"]),
            )
        )
        job = result.scalar_one_or_none()
        if not job:
            return AgentResponse(text="У вас нет активных заданий.", intent="cancel")

        job.status = "cancelled"
        await db.commit()
        cleanup_job(job.id)

        return AgentResponse(text="🚫 Задание отменено.", intent="cancel")

    def _help_text(self) -> str:
        return (
            "🎬 <b>Video Shorts Bot</b>\n\n"
            "Я нарезаю YouTube видео на шортсы. Вот что я умею:\n\n"
            "📌 <b>Отправьте ссылку</b> на YouTube видео\n"
            "   Я скачаю, проанализирую и предложу интересные моменты\n\n"
            "📌 <b>Подтвердите или отредактируйте</b> сегменты\n"
            "   Используйте кнопки или напишите:\n"
            "   • «подтвердить» — нарезать все\n"
            "   • «удали 2» — убрать сегмент\n"
            "   • «измени 1 с 0:15 до 0:45» — изменить тайминг\n"
            "   • «отмена» — отменить\n\n"
            "📌 <b>Статус</b> — спросите «статус» или «как дела?»\n\n"
            "⚠️ Максимальная длительность видео: 30 минут"
        )
