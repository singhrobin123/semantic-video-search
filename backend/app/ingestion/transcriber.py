"""
Video transcript extraction.

Supports two sources:
  1. **YouTube** — via ``youtube-transcript-api`` (no API key required).
  2. **Manual upload** — accepts pre-formatted transcript JSON.

This module is intentionally decoupled from the embedding and storage layers
so it can be swapped for Whisper-based transcription in the future.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TranscriptSegment:
    """A single captioned segment from a video."""
    text: str
    start: float          # seconds
    duration: float       # seconds

    @property
    def end(self) -> float:
        return self.start + self.duration


def extract_youtube_id(url_or_id: str) -> str:
    """
    Accept a YouTube URL or bare video ID and return the 11-character ID.

    Handles:
      - https://www.youtube.com/watch?v=XXXXXXXXXXX
      - https://youtu.be/XXXXXXXXXXX
      - XXXXXXXXXXX (bare ID)
    """
    patterns = [
        r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"^([a-zA-Z0-9_-]{11})$",
    ]
    for pat in patterns:
        match = re.search(pat, url_or_id)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract YouTube video ID from: {url_or_id}")


async def fetch_youtube_transcript(
    url_or_id: str,
    languages: list[str] | None = None,
) -> tuple[list[TranscriptSegment], dict[str, str]]:
    """
    Fetch the transcript for a YouTube video.

    Returns:
        (segments, metadata) where metadata contains video_id, title, etc.
    """
    from youtube_transcript_api import YouTubeTranscriptApi

    video_id = extract_youtube_id(url_or_id)
    lang = languages or ["en"]

    logger.info("fetching_youtube_transcript", video_id=video_id, languages=lang)

    try:
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id, languages=lang)
    except Exception as exc:
        logger.error("youtube_transcript_fetch_failed", video_id=video_id, error=str(exc))
        raise ValueError(
            f"Could not fetch transcript for video {video_id}: {type(exc).__name__}. "
            "The video may be private, have no captions, or YouTube may be blocking requests."
        ) from exc

    segments = [
        TranscriptSegment(
            text=entry.text.strip(),
            start=entry.start,
            duration=entry.duration,
        )
        for entry in transcript
        if entry.text.strip()
    ]

    metadata = {
        "video_id": video_id,
        "source_url": f"https://www.youtube.com/watch?v={video_id}",
        "language": lang[0],
    }

    logger.info(
        "youtube_transcript_fetched",
        video_id=video_id,
        segments=len(segments),
        total_duration=segments[-1].end if segments else 0,
    )
    return segments, metadata


async def fetch_youtube_metadata(video_id: str) -> dict[str, str]:
    """
    Fetch video title and channel via yt-dlp (lightweight metadata-only).

    Falls back to a placeholder if yt-dlp is unavailable.
    """
    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}", download=False
            )
            return {
                "title": info.get("title", f"YouTube Video {video_id}"),
                "channel_name": info.get("channel", info.get("uploader", "")),
                "duration_seconds": info.get("duration", 0),
                "description": (info.get("description") or "")[:500],
            }
    except ImportError:
        logger.warning("yt_dlp_not_installed_using_fallback")
        return {
            "title": f"YouTube Video {video_id}",
            "channel_name": "",
            "duration_seconds": 0,
            "description": "",
        }
    except Exception as exc:
        logger.warning("yt_dlp_metadata_failed", error=str(exc))
        return {
            "title": f"YouTube Video {video_id}",
            "channel_name": "",
            "duration_seconds": 0,
            "description": "",
        }
