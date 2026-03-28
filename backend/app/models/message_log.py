from datetime import datetime

from sqlalchemy import String, BigInteger, ForeignKey, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MessageLog(Base):
    __tablename__ = "message_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"))
    telegram_id: Mapped[int] = mapped_column(BigInteger)
    direction: Mapped[str] = mapped_column(String(10))  # incoming / outgoing
    message_type: Mapped[str] = mapped_column(String(20))  # text / voice / system
    content_text: Mapped[str | None] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(100))
    intent_data: Mapped[dict | None] = mapped_column(JSON)
    response_text: Mapped[str | None] = mapped_column(Text)
    processing_ms: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
