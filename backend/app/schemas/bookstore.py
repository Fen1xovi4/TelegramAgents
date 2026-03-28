from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class BookCreate(BaseModel):
    title: str
    author: str | None = None
    genre: str | None = None
    isbn: str | None = None
    description: str | None = None
    quantity: int = 0
    price: Decimal | None = None


class BookUpdate(BaseModel):
    title: str | None = None
    author: str | None = None
    genre: str | None = None
    isbn: str | None = None
    description: str | None = None
    quantity: int | None = None
    price: Decimal | None = None


class BookResponse(BaseModel):
    id: int
    agent_id: int
    title: str
    author: str | None
    genre: str | None
    isbn: str | None
    description: str | None
    quantity: int
    price: Decimal | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InventoryLogResponse(BaseModel):
    id: int
    book_id: int
    agent_id: int
    change_type: str
    quantity_change: int
    note: str | None
    performed_by: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
