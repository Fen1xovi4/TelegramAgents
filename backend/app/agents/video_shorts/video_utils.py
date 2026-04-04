import asyncio
import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

VIDEO_TMP_DIR = Path("/tmp/video_shorts")


def job_dir(job_id: int) -> Path:
    """Return temp directory for a specific job."""
    d = VIDEO_TMP_DIR / str(job_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


async def get_video_info(url: str) -> dict:
    """Get video metadata without downloading (title, duration, etc.)."""
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp", "--dump-json", "--no-download",
        "--impersonate", "chrome",
        "--js-runtimes", "node",
        "--remote-components", "ejs:github",
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp info failed: {stderr.decode()}")

    return json.loads(stdout.decode())


async def download_video(url: str, output_dir: Path) -> dict:
    """Download video at max 720p. Returns metadata dict with filepath."""
    output_path = str(output_dir / "source.%(ext)s")

    proc = await asyncio.create_subprocess_exec(
        "yt-dlp",
        "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "--merge-output-format", "mp4",
        "--write-auto-sub", "--write-sub",
        "--sub-lang", "ru,en",
        "--sub-format", "vtt",
        "--no-playlist",
        "--max-filesize", "500M",
        "--impersonate", "chrome",
        "--js-runtimes", "node",
        "--remote-components", "ejs:github",
        "--ignore-errors",
        "-o", output_path,
        "--print-json",
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp download failed: {stderr.decode()}")

    if not stdout.strip():
        raise RuntimeError(f"yt-dlp produced no output: {stderr.decode()}")

    info = json.loads(stdout.decode())

    # Find the actual downloaded file
    video_path = None
    for f in output_dir.iterdir():
        if f.suffix == ".mp4" and f.stem.startswith("source"):
            video_path = f
            break

    if not video_path:
        # Fallback: use filename from yt-dlp info
        ext = info.get("ext", "mp4")
        video_path = output_dir / f"source.{ext}"

    return {
        "title": info.get("title", "Unknown"),
        "duration": info.get("duration", 0),
        "filepath": str(video_path),
    }


async def extract_audio(video_path: str, output_path: str) -> str:
    """Extract audio from video using ffmpeg."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-i", video_path,
        "-vn", "-acodec", "libopus", "-b:a", "64k",
        "-y", output_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extraction failed: {stderr.decode()}")

    return output_path


async def cut_segment(video_path: str, start: float, end: float, output_path: str) -> str:
    """Cut a video segment using ffmpeg. Tries copy first, re-encodes on failure."""
    # Try fast copy first
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-i", video_path,
        "-ss", str(start), "-to", str(end),
        "-c", "copy", "-y", output_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode == 0:
        return output_path

    logger.warning("Fast copy cut failed, re-encoding segment...")

    # Re-encode fallback
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-i", video_path,
        "-ss", str(start), "-to", str(end),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-y", output_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg segment cut failed: {stderr.decode()}")

    return output_path


def find_subtitles(output_dir: Path) -> str | None:
    """Find downloaded subtitle file in the job directory."""
    for f in output_dir.iterdir():
        if f.suffix in (".vtt", ".srt"):
            return str(f)
    return None


def parse_vtt(vtt_path: str) -> list[dict]:
    """Parse VTT subtitle file into timestamped segments."""
    with open(vtt_path, "r", encoding="utf-8") as f:
        content = f.read()

    segments = []
    # Match VTT cue blocks: timestamp --> timestamp \n text
    pattern = r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})\s*\n(.+?)(?=\n\n|\Z)"
    for match in re.finditer(pattern, content, re.DOTALL):
        start_str, end_str, text = match.groups()
        # Clean HTML tags and positioning info
        text = re.sub(r"<[^>]+>", "", text).strip()
        text = re.sub(r"align:.*|position:.*", "", text).strip()
        if not text:
            continue
        segments.append({
            "start": _vtt_time_to_seconds(start_str),
            "end": _vtt_time_to_seconds(end_str),
            "text": text,
        })

    return segments


def _vtt_time_to_seconds(time_str: str) -> float:
    """Convert VTT timestamp (HH:MM:SS.mmm) to seconds."""
    parts = time_str.split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds


def format_transcript_with_timestamps(segments: list[dict]) -> str:
    """Format subtitle segments into timestamped transcript for LLM analysis."""
    lines = []
    for seg in segments:
        start_min = int(seg["start"] // 60)
        start_sec = int(seg["start"] % 60)
        lines.append(f"[{start_min:02d}:{start_sec:02d}] {seg['text']}")
    return "\n".join(lines)


def cleanup_job(job_id: int):
    """Remove all temporary files for a job."""
    import shutil
    d = VIDEO_TMP_DIR / str(job_id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
        logger.info(f"Cleaned up job directory: {d}")
