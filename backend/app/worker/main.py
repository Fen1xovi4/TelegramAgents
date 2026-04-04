import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from arq.connections import RedisSettings
from arq.cron import cron
from sqlalchemy import select, update

from app.config import settings
from app.agents.video_shorts.jobs import download_and_analyze, cut_and_send
from app.agents.video_shorts.video_utils import VIDEO_TMP_DIR

logger = logging.getLogger(__name__)


async def startup(ctx):
    pass


async def shutdown(ctx):
    pass


async def cleanup_old_videos(ctx):
    """Clean up temp video files older than 24h and mark stale jobs as failed."""
    from app.database import async_session
    from app.models.video_job import VideoJob

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    # Mark stale processing jobs as failed
    async with async_session() as db:
        stale_cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        await db.execute(
            update(VideoJob)
            .where(
                VideoJob.status.in_(["downloading", "transcribing", "analyzing", "cutting", "sending"]),
                VideoJob.updated_at < stale_cutoff,
            )
            .values(status="failed", error_message="Job timed out")
        )
        await db.commit()

    # Clean up old directories
    if VIDEO_TMP_DIR.exists():
        for d in VIDEO_TMP_DIR.iterdir():
            if d.is_dir():
                try:
                    mtime = datetime.fromtimestamp(d.stat().st_mtime, tz=timezone.utc)
                    if mtime < cutoff:
                        shutil.rmtree(d, ignore_errors=True)
                        logger.info(f"Cleaned up old video dir: {d}")
                except Exception as e:
                    logger.warning(f"Failed to clean up {d}: {e}")


class WorkerSettings:
    functions = [download_and_analyze, cut_and_send]
    cron_jobs = [cron(cleanup_old_videos, hour=3, minute=0)]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 3
    job_timeout = 600  # 10 minutes per job
