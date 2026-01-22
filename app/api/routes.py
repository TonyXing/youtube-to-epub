import asyncio
import uuid
import traceback
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

from app.models.schemas import (
    ConvertRequest,
    ConvertResponse,
    VideoPreview,
    ConversionStatus,
    ProcessedVideo,
)
from app.services.youtube_service import (
    get_video_preview,
    get_video_metadata,
    get_transcript,
    get_transcript_text,
    YouTubeServiceError,
)
from app.services.chapter_service import detect_chapters
from app.services.summarization_service import (
    generate_overall_summary,
    generate_all_chapter_summaries,
)
from app.services.epub_service import create_epub
from app.services.progress_service import progress_service


router = APIRouter(prefix="/api/v1")


@router.get("/preview", response_model=VideoPreview)
async def preview_video(url: str):
    """Preview video information before conversion."""
    try:
        preview = await get_video_preview(url)
        return preview
    except YouTubeServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch video info: {str(e)}")


@router.post("/convert", response_model=ConvertResponse)
async def start_conversion(request: ConvertRequest, background_tasks: BackgroundTasks):
    """Start video conversion process."""
    job_id = str(uuid.uuid4())
    progress_service.create_job(job_id)

    # Run conversion in background
    background_tasks.add_task(run_conversion, job_id, request.url)

    return ConvertResponse(
        job_id=job_id,
        message="Conversion started",
    )


@router.get("/convert/{job_id}/progress")
async def get_progress(job_id: str):
    """Stream conversion progress via SSE."""
    job = progress_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    queue = progress_service.subscribe(job_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        try:
            # Send initial state
            yield {
                "event": "progress",
                "data": f'{{"job_id": "{job_id}", "status": "{job.status.value}", "progress": {job.progress}, "message": "{job.message}"}}',
            }

            # Stream updates
            while True:
                try:
                    update = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {
                        "event": "progress",
                        "data": update.model_dump_json(),
                    }

                    # Stop streaming when job is complete or failed
                    if update.status in [ConversionStatus.COMPLETED, ConversionStatus.FAILED]:
                        break
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {"event": "ping", "data": ""}
        finally:
            progress_service.unsubscribe(job_id, queue)

    return EventSourceResponse(event_generator())


@router.get("/convert/{job_id}/download")
async def download_epub(job_id: str):
    """Download the generated EPUB file."""
    result = progress_service.get_job_result(job_id)

    if not result:
        raise HTTPException(status_code=404, detail="Job not found")

    if result.status == ConversionStatus.FAILED:
        raise HTTPException(status_code=400, detail=result.error or "Conversion failed")

    if result.status != ConversionStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Conversion not complete")

    if not result.file_path or not Path(result.file_path).exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=result.file_path,
        filename=result.file_name,
        media_type="application/epub+zip",
    )


async def run_conversion(job_id: str, url: str):
    """Run the full conversion pipeline."""
    try:
        # Step 1: Validate and fetch metadata
        await progress_service.update_progress(
            job_id,
            ConversionStatus.FETCHING_METADATA,
            "Fetching video metadata...",
            0,
        )

        metadata = await get_video_metadata(url)

        await progress_service.update_progress(
            job_id,
            ConversionStatus.FETCHING_METADATA,
            f"Found: {metadata.title}",
            1.0,
        )

        # Step 2: Fetch transcript
        await progress_service.update_progress(
            job_id,
            ConversionStatus.FETCHING_TRANSCRIPT,
            "Fetching transcript...",
            0,
        )

        transcript = await get_transcript(metadata.video_id)

        await progress_service.update_progress(
            job_id,
            ConversionStatus.FETCHING_TRANSCRIPT,
            f"Transcript loaded ({len(transcript)} segments)",
            1.0,
        )

        # Step 3: Detect chapters
        await progress_service.update_progress(
            job_id,
            ConversionStatus.DETECTING_CHAPTERS,
            "Detecting chapters...",
            0,
        )

        chapters = await detect_chapters(metadata, transcript)

        await progress_service.update_progress(
            job_id,
            ConversionStatus.DETECTING_CHAPTERS,
            f"Found {len(chapters)} chapters",
            1.0,
        )

        # Step 4: Generate summaries
        await progress_service.update_progress(
            job_id,
            ConversionStatus.GENERATING_SUMMARIES,
            "Generating overall summary...",
            0,
        )

        full_transcript = get_transcript_text(transcript)
        overall_summary = await generate_overall_summary(metadata, full_transcript)

        await progress_service.update_progress(
            job_id,
            ConversionStatus.GENERATING_SUMMARIES,
            "Generating chapter summaries...",
            0.3,
        )

        # Progress callback for chapter summaries
        async def chapter_progress(completed: int, total: int):
            progress = 0.3 + (0.7 * completed / total)
            await progress_service.update_progress(
                job_id,
                ConversionStatus.GENERATING_SUMMARIES,
                f"Summarizing chapter {completed}/{total}...",
                progress,
            )

        chapters = await generate_all_chapter_summaries(chapters, chapter_progress)

        # Step 5: Create EPUB
        await progress_service.update_progress(
            job_id,
            ConversionStatus.CREATING_EPUB,
            "Creating EPUB file...",
            0,
        )

        processed_video = ProcessedVideo(
            metadata=metadata,
            transcript=transcript,
            chapters=chapters,
            overall_summary=overall_summary,
        )

        epub_path = create_epub(processed_video)

        await progress_service.update_progress(
            job_id,
            ConversionStatus.CREATING_EPUB,
            "EPUB created successfully",
            1.0,
        )

        # Mark as completed
        await progress_service.set_completed(
            job_id,
            str(epub_path),
            epub_path.name,
        )

    except YouTubeServiceError as e:
        print(f"[ERROR] YouTube service error: {e}")
        await progress_service.set_error(job_id, str(e))
    except Exception as e:
        print(f"[ERROR] Conversion failed: {e}")
        traceback.print_exc()
        await progress_service.set_error(job_id, f"Conversion failed: {str(e)}")
