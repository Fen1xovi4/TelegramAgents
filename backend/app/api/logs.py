from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.message_log import MessageLog
from app.models.user import User
from app.api.deps import get_current_user
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/api/agents", tags=["logs"])


class MessageLogResponse(BaseModel):
    id: int
    agent_id: int
    telegram_id: int
    direction: str
    message_type: str
    content_text: str | None
    intent: str | None
    intent_data: dict | None
    response_text: str | None
    processing_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedLogs(BaseModel):
    items: list[MessageLogResponse]
    total: int
    page: int
    per_page: int


@router.get("/{agent_id}/logs", response_model=PaginatedLogs)
async def get_agent_logs(
    agent_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    offset = (page - 1) * per_page

    count_result = await db.execute(
        select(func.count()).select_from(MessageLog).where(MessageLog.agent_id == agent_id)
    )
    total = count_result.scalar()

    result = await db.execute(
        select(MessageLog)
        .where(MessageLog.agent_id == agent_id)
        .order_by(MessageLog.id.desc())
        .offset(offset)
        .limit(per_page)
    )
    items = result.scalars().all()

    return PaginatedLogs(items=items, total=total, page=page, per_page=per_page)
