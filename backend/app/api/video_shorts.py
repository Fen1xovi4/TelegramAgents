from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.video_job import VideoJob
from app.models.user import User
from app.schemas.video_shorts import VideoJobResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/agents/{agent_id}/video-jobs", tags=["video_shorts"])


@router.get("", response_model=list[VideoJobResponse])
async def list_video_jobs(
    agent_id: int,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(VideoJob)
        .where(VideoJob.agent_id == agent_id)
        .order_by(VideoJob.id.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{job_id}", response_model=VideoJobResponse)
async def get_video_job(
    agent_id: int,
    job_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(VideoJob).where(VideoJob.id == job_id, VideoJob.agent_id == agent_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")
    return job
