from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.bookstore import Book, InventoryLog
from app.models.user import User
from app.schemas.bookstore import BookCreate, BookUpdate, BookResponse, InventoryLogResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/agents/{agent_id}/bookstore", tags=["bookstore"])


@router.get("/books", response_model=list[BookResponse])
async def list_books(agent_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Book).where(Book.agent_id == agent_id).order_by(Book.title))
    return result.scalars().all()


@router.post("/books", response_model=BookResponse, status_code=201)
async def create_book(
    agent_id: int, body: BookCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    book = Book(agent_id=agent_id, **body.model_dump())
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


@router.put("/books/{book_id}", response_model=BookResponse)
async def update_book(
    agent_id: int,
    book_id: int,
    body: BookUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Book).where(Book.id == book_id, Book.agent_id == agent_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(book, field, value)
    await db.commit()
    await db.refresh(book)
    return book


@router.delete("/books/{book_id}", status_code=204)
async def delete_book(
    agent_id: int,
    book_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Book).where(Book.id == book_id, Book.agent_id == agent_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    await db.delete(book)
    await db.commit()


@router.get("/inventory-log", response_model=list[InventoryLogResponse])
async def get_inventory_log(
    agent_id: int,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(InventoryLog)
        .where(InventoryLog.agent_id == agent_id)
        .order_by(InventoryLog.id.desc())
        .limit(limit)
    )
    return result.scalars().all()
