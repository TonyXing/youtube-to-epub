import asyncio
import json
import tiktoken
from openai import AsyncOpenAI

from app.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    MAX_TOKENS_PER_CHUNK,
    TOKEN_OVERLAP,
)
from app.models.schemas import VideoMetadata, VideoChapter, OverallSummary


# Initialize tiktoken encoder
ENCODING = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken."""
    return len(ENCODING.encode(text))


def chunk_text(text: str, max_tokens: int = MAX_TOKENS_PER_CHUNK, overlap: int = TOKEN_OVERLAP) -> list[str]:
    """Split text into chunks that fit within token limits."""
    tokens = ENCODING.encode(text)

    if len(tokens) <= max_tokens:
        return [text]

    chunks = []
    start = 0

    while start < len(tokens):
        end = start + max_tokens
        chunk_tokens = tokens[start:end]
        chunk_text = ENCODING.decode(chunk_tokens)
        chunks.append(chunk_text)

        # Move start forward, accounting for overlap
        start = end - overlap

    return chunks


async def generate_overall_summary(
    metadata: VideoMetadata,
    full_transcript: str,
) -> OverallSummary:
    """Generate overall video summary with key takeaways."""
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    # Chunk transcript if needed
    chunks = chunk_text(full_transcript)

    # If multiple chunks, summarize each first then combine
    if len(chunks) > 1:
        chunk_summaries = await asyncio.gather(*[
            _summarize_chunk(client, chunk, i, len(chunks))
            for i, chunk in enumerate(chunks)
        ])
        combined_text = "\n\n".join(chunk_summaries)
    else:
        combined_text = full_transcript

    # Generate final summary
    prompt = f"""Analyze this video content and create a comprehensive summary.

Video: "{metadata.title}" by {metadata.channel}
Duration: {metadata.duration // 60} minutes

Content:
{combined_text[:15000]}

Provide:
1. An overview (2-3 paragraphs) that captures the main points
2. 5-7 key takeaways as bullet points

Respond with ONLY valid JSON in this exact format:
{{
  "overview": "Your overview paragraphs here...",
  "key_takeaways": [
    "First key takeaway",
    "Second key takeaway",
    ...
  ]
}}"""

    response = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are an expert content summarizer. Create clear, informative summaries. Respond only with valid JSON."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
    )

    content = response.choices[0].message.content.strip()

    # Extract JSON from response
    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    try:
        data = json.loads(content)
        return OverallSummary(
            overview=data["overview"],
            key_takeaways=data["key_takeaways"],
        )
    except json.JSONDecodeError:
        # Fallback if JSON parsing fails
        return OverallSummary(
            overview=content[:1000],
            key_takeaways=["Summary generation encountered an error. Please refer to the transcript."],
        )


async def _summarize_chunk(client: AsyncOpenAI, chunk: str, index: int, total: int) -> str:
    """Summarize a single chunk of text."""
    prompt = f"""Summarize this portion of a video transcript (part {index + 1} of {total}).
Focus on the key points and main ideas.

Transcript:
{chunk}

Provide a concise summary (2-3 paragraphs)."""

    response = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are an expert content summarizer. Create clear, informative summaries."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
    )

    return response.choices[0].message.content.strip()


async def generate_chapter_summary(chapter: VideoChapter) -> str:
    """Generate a summary for a single chapter."""
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    # Handle long chapter transcripts
    transcript = chapter.transcript
    if count_tokens(transcript) > MAX_TOKENS_PER_CHUNK:
        # Truncate for summary
        tokens = ENCODING.encode(transcript)[:MAX_TOKENS_PER_CHUNK]
        transcript = ENCODING.decode(tokens) + "..."

    prompt = f"""Summarize this chapter of a video.

Chapter: "{chapter.title}"
Transcript:
{transcript}

Provide a concise summary (1-2 paragraphs) capturing the main points of this chapter."""

    response = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are an expert content summarizer. Create clear, informative chapter summaries."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
    )

    return response.choices[0].message.content.strip()


async def generate_all_chapter_summaries(
    chapters: list[VideoChapter],
    progress_callback=None,
) -> list[VideoChapter]:
    """Generate summaries for all chapters with rate limiting."""
    # Process chapters concurrently but with a limit
    semaphore = asyncio.Semaphore(3)  # Max 3 concurrent requests

    async def process_chapter(i: int, chapter: VideoChapter) -> VideoChapter:
        async with semaphore:
            summary = await generate_chapter_summary(chapter)
            chapter.summary = summary

            if progress_callback:
                await progress_callback(i + 1, len(chapters))

            return chapter

    tasks = [process_chapter(i, ch) for i, ch in enumerate(chapters)]
    return await asyncio.gather(*tasks)
