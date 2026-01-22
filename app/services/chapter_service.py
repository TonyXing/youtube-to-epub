import json
from openai import AsyncAzureOpenAI

from app.config import (
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_OPENAI_API_VERSION,
    SHORT_VIDEO_THRESHOLD_MINUTES,
)
from app.models.schemas import VideoMetadata, VideoChapter, TranscriptSegment
from app.services.youtube_service import get_transcript_for_timerange, get_transcript_text


def get_azure_client() -> AsyncAzureOpenAI:
    """Create Azure OpenAI client."""
    return AsyncAzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
    )


async def detect_chapters(
    metadata: VideoMetadata,
    transcript: list[TranscriptSegment],
) -> list[VideoChapter]:
    """
    Detect chapters for a video.

    Logic:
    1. Use video chapters if available
    2. For short videos (<15 min), use single chapter
    3. For long videos, use AI-based segmentation
    """
    # If video has chapters, use them and populate transcript
    if metadata.chapters:
        chapters = []
        for chapter in metadata.chapters:
            chapter_transcript = get_transcript_for_timerange(
                transcript,
                chapter.start_time,
                chapter.end_time,
            )
            chapters.append(VideoChapter(
                title=chapter.title,
                start_time=chapter.start_time,
                end_time=chapter.end_time,
                transcript=chapter_transcript,
            ))
        return chapters

    full_transcript = get_transcript_text(transcript)
    duration_minutes = metadata.duration / 60

    # For short videos, use single chapter
    if duration_minutes < SHORT_VIDEO_THRESHOLD_MINUTES:
        return [VideoChapter(
            title=metadata.title,
            start_time=0,
            end_time=metadata.duration,
            transcript=full_transcript,
        )]

    # For long videos, use AI-based segmentation
    return await ai_segment_chapters(metadata, transcript, full_transcript)


async def ai_segment_chapters(
    metadata: VideoMetadata,
    transcript: list[TranscriptSegment],
    full_transcript: str,
) -> list[VideoChapter]:
    """Use AI to segment a long video into logical chapters."""
    client = get_azure_client()

    # Truncate transcript if too long for context
    max_chars = 30000
    truncated_transcript = full_transcript[:max_chars]
    if len(full_transcript) > max_chars:
        truncated_transcript += "... [transcript truncated]"

    prompt = f"""Analyze this video transcript and identify logical chapter breaks.
The video is "{metadata.title}" by {metadata.channel}, {metadata.duration // 60} minutes long.

Transcript:
{truncated_transcript}

Create 3-7 logical chapters based on topic changes in the content.
For each chapter, provide:
1. A descriptive title (not just "Chapter 1")
2. The approximate start time as a percentage of the video (0-100)

Respond with ONLY a JSON array in this exact format:
[
  {{"title": "Introduction", "start_percent": 0}},
  {{"title": "Main Topic", "start_percent": 15}},
  ...
]"""

    try:
        response = await client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes video transcripts and identifies logical chapter breaks. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        content = response.choices[0].message.content.strip()

        # Extract JSON from response (handle markdown code blocks)
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        chapter_data = json.loads(content)

        # Convert percentages to actual timestamps and create chapters
        chapters = []
        for i, ch in enumerate(chapter_data):
            start_time = (ch["start_percent"] / 100) * metadata.duration

            # Calculate end time (next chapter start or video end)
            if i < len(chapter_data) - 1:
                end_time = (chapter_data[i + 1]["start_percent"] / 100) * metadata.duration
            else:
                end_time = metadata.duration

            # Get transcript for this chapter
            chapter_transcript = get_transcript_for_timerange(
                transcript,
                start_time,
                end_time,
            )

            chapters.append(VideoChapter(
                title=ch["title"],
                start_time=start_time,
                end_time=end_time,
                transcript=chapter_transcript,
            ))

        return chapters

    except Exception as e:
        # Fallback to single chapter if AI segmentation fails
        return [VideoChapter(
            title=metadata.title,
            start_time=0,
            end_time=metadata.duration,
            transcript=full_transcript,
        )]
