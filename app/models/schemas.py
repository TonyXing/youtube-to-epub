from pydantic import BaseModel, Field, field_validator
from typing import Optional
from enum import Enum
import re


class ConversionStatus(str, Enum):
    VALIDATING = "validating"
    FETCHING_METADATA = "fetching_metadata"
    FETCHING_TRANSCRIPT = "fetching_transcript"
    DETECTING_CHAPTERS = "detecting_chapters"
    GENERATING_SUMMARIES = "generating_summaries"
    CREATING_EPUB = "creating_epub"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoChapter(BaseModel):
    title: str
    start_time: float  # seconds
    end_time: Optional[float] = None
    transcript: str = ""
    summary: str = ""


class TranscriptSegment(BaseModel):
    text: str
    start: float
    duration: float


class VideoMetadata(BaseModel):
    video_id: str
    title: str
    channel: str
    duration: int  # seconds
    thumbnail_url: Optional[str] = None
    chapters: list[VideoChapter] = []
    publish_date: Optional[str] = None


class VideoPreview(BaseModel):
    video_id: str
    title: str
    channel: str
    duration: int
    duration_formatted: str
    thumbnail_url: Optional[str] = None
    has_chapters: bool
    chapter_count: int


class ConvertRequest(BaseModel):
    url: str = Field(..., description="YouTube video URL")

    @field_validator("url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        youtube_patterns = [
            r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})",
            r"(?:https?://)?(?:www\.)?youtu\.be/([a-zA-Z0-9_-]{11})",
            r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})",
        ]
        for pattern in youtube_patterns:
            if re.match(pattern, v):
                return v
        raise ValueError("Invalid YouTube URL")


class ConvertResponse(BaseModel):
    job_id: str
    message: str


class ProgressUpdate(BaseModel):
    job_id: str
    status: ConversionStatus
    progress: int  # 0-100
    message: str
    error: Optional[str] = None


class JobResult(BaseModel):
    job_id: str
    status: ConversionStatus
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    error: Optional[str] = None


class OverallSummary(BaseModel):
    overview: str
    key_takeaways: list[str]


class ProcessedVideo(BaseModel):
    metadata: VideoMetadata
    transcript: list[TranscriptSegment]
    chapters: list[VideoChapter]
    overall_summary: OverallSummary
