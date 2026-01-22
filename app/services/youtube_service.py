import re
from typing import Optional
from youtube_transcript_api import YouTubeTranscriptApi
from pytubefix import YouTube

from app.models.schemas import (
    VideoMetadata,
    VideoChapter,
    TranscriptSegment,
    VideoPreview,
)


class YouTubeServiceError(Exception):
    """Base exception for YouTube service errors."""
    pass


class VideoNotFoundError(YouTubeServiceError):
    """Raised when video is not found."""
    pass


class TranscriptNotAvailableError(YouTubeServiceError):
    """Raised when transcript is not available."""
    pass


def extract_video_id(url: str) -> str:
    """Extract video ID from various YouTube URL formats."""
    patterns = [
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})",
        r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from URL: {url}")


def format_duration(seconds: int) -> str:
    """Format duration in seconds to human-readable string."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


async def get_video_metadata(url: str) -> VideoMetadata:
    """Fetch video metadata using pytubefix."""
    try:
        video_id = extract_video_id(url)
        yt = YouTube(url)

        # Extract chapters if available
        chapters = []
        if yt.chapters:
            for i, chapter in enumerate(yt.chapters):
                end_time = None
                if i < len(yt.chapters) - 1:
                    end_time = yt.chapters[i + 1].start_seconds
                else:
                    end_time = yt.length

                chapters.append(VideoChapter(
                    title=chapter.title,
                    start_time=chapter.start_seconds,
                    end_time=end_time,
                ))

        # Get publish date
        publish_date = None
        if yt.publish_date:
            publish_date = yt.publish_date.strftime("%Y-%m-%d")

        return VideoMetadata(
            video_id=video_id,
            title=yt.title,
            channel=yt.author,
            duration=yt.length,
            thumbnail_url=yt.thumbnail_url,
            chapters=chapters,
            publish_date=publish_date,
        )
    except Exception as e:
        raise VideoNotFoundError(f"Failed to fetch video metadata: {str(e)}")


async def get_video_preview(url: str) -> VideoPreview:
    """Get video preview information."""
    metadata = await get_video_metadata(url)

    return VideoPreview(
        video_id=metadata.video_id,
        title=metadata.title,
        channel=metadata.channel,
        duration=metadata.duration,
        duration_formatted=format_duration(metadata.duration),
        thumbnail_url=metadata.thumbnail_url,
        has_chapters=len(metadata.chapters) > 0,
        chapter_count=len(metadata.chapters),
    )


async def get_transcript(video_id: str) -> list[TranscriptSegment]:
    """Fetch transcript for a video."""
    try:
        # New API in youtube-transcript-api v1.x - instance-based
        api = YouTubeTranscriptApi()

        # Try English variants, then fall back to any available
        try:
            transcript_data = api.fetch(video_id, languages=['en', 'en-US', 'en-GB'])
        except:
            # Fall back to any available transcript
            transcript_list = api.list(video_id)
            transcript = next(iter(transcript_list))
            transcript_data = transcript.fetch()

        return [
            TranscriptSegment(
                text=segment.text,
                start=segment.start,
                duration=segment.duration,
            )
            for segment in transcript_data
        ]
    except Exception as e:
        raise TranscriptNotAvailableError(f"Failed to fetch transcript: {str(e)}")


def get_transcript_text(segments: list[TranscriptSegment]) -> str:
    """Combine transcript segments into full text."""
    return " ".join(segment.text for segment in segments)


def get_transcript_for_timerange(
    segments: list[TranscriptSegment],
    start_time: float,
    end_time: Optional[float] = None,
) -> str:
    """Get transcript text for a specific time range."""
    result = []
    for segment in segments:
        segment_end = segment.start + segment.duration

        # Check if segment overlaps with the time range
        if end_time is not None:
            if segment.start < end_time and segment_end > start_time:
                result.append(segment.text)
        else:
            if segment.start >= start_time:
                result.append(segment.text)

    return " ".join(result)
