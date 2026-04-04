from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, BigInteger, ForeignKey, JSON, Text, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Book(Base, TimestampMixin):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(20), default="sale")  # sale / rental
    title: Mapped[str] = mapped_column(String(500))
    author: Mapped[str | None] = mapped_column(String(500))
    genre: Mapped[str | None] = mapped_column(String(100))
    isbn: Mapped[str | None] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[int] = mapped_column(default=0)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class InventoryLog(Base):
    __tablename__ = "inventory_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"))
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id", ondelete="CASCADE"))
    change_type: Mapped[str] = mapped_column(String(20))  # arrival / sale / adjustment
    quantity_change: Mapped[int] = mapped_column()
    note: Mapped[str | None] = mapped_column(Text)
    performed_by: Mapped[int | None] = mapped_column(BigInteger)  # telegram_id
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
