from sqlalchemy import BigInteger, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class VideoJob(Base, TimestampMixin):
    __tablename__ = "video_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"))
    telegram_id: Mapped[int] = mapped_column(BigInteger)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    youtube_url: Mapped[str] = mapped_column(String(512))
    video_title: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(50), default="downloading")
    # [{"id": 1, "start": 12.5, "end": 55.0, "title": "...", "reason": "..."}]
    segments: Mapped[dict | None] = mapped_column(JSON)
    approved_segments: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    video_path: Mapped[str | None] = mapped_column(String(1024))
    transcript_text: Mapped[str | None] = mapped_column(Text)
