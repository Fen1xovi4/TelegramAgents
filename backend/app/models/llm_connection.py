from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class LLMConnection(Base, TimestampMixin):
    __tablename__ = "llm_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))                # "GPT-4o Mini для ответов"
    provider: Mapped[str] = mapped_column(String(50))             # openai / anthropic
    api_key: Mapped[str] = mapped_column(Text)                    # encrypted in future
    model: Mapped[str] = mapped_column(String(100))               # gpt-4o-mini, claude-haiku-4-5, etc.
    purpose: Mapped[str] = mapped_column(String(50))              # chat / stt
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
