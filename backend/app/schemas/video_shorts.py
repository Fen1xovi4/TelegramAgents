from datetime import datetime

from pydantic import BaseModel


class VideoJobResponse(BaseModel):
    id: int
    agent_id: int
    telegram_id: int
    youtube_url: str
    video_title: str | None
    status: str
    segments: list | None
    approved_segments: list | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
