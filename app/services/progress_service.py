import asyncio
from typing import Optional
from dataclasses import dataclass, field

from app.config import PROGRESS_STEPS
from app.models.schemas import ConversionStatus, ProgressUpdate, JobResult


@dataclass
class Job:
    """Represents a conversion job."""
    job_id: str
    status: ConversionStatus = ConversionStatus.VALIDATING
    progress: int = 0
    message: str = "Starting conversion..."
    error: Optional[str] = None
    file_path: Optional[str] = None
    file_name: Optional[str] = None
    subscribers: list[asyncio.Queue] = field(default_factory=list)


class ProgressService:
    """Service for tracking conversion progress and broadcasting updates."""

    def __init__(self):
        self._jobs: dict[str, Job] = {}

    def create_job(self, job_id: str) -> Job:
        """Create a new conversion job."""
        job = Job(job_id=job_id)
        self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    async def update_progress(
        self,
        job_id: str,
        status: ConversionStatus,
        message: str,
        sub_progress: float = 0,
    ):
        """Update job progress and notify subscribers."""
        job = self._jobs.get(job_id)
        if not job:
            return

        job.status = status
        job.message = message

        # Calculate overall progress based on step and sub-progress
        if status.value in PROGRESS_STEPS:
            start, end = PROGRESS_STEPS[status.value]
            job.progress = int(start + (end - start) * sub_progress)
        else:
            job.progress = 0

        # Notify all subscribers
        await self._notify_subscribers(job)

    async def set_error(self, job_id: str, error: str):
        """Set job to error state."""
        job = self._jobs.get(job_id)
        if not job:
            return

        job.status = ConversionStatus.FAILED
        job.error = error
        job.message = f"Error: {error}"

        await self._notify_subscribers(job)

    async def set_completed(self, job_id: str, file_path: str, file_name: str):
        """Mark job as completed."""
        job = self._jobs.get(job_id)
        if not job:
            return

        job.status = ConversionStatus.COMPLETED
        job.progress = 100
        job.message = "Conversion complete!"
        job.file_path = file_path
        job.file_name = file_name

        await self._notify_subscribers(job)

    def subscribe(self, job_id: str) -> Optional[asyncio.Queue]:
        """Subscribe to job updates. Returns a queue for receiving updates."""
        job = self._jobs.get(job_id)
        if not job:
            return None

        queue: asyncio.Queue = asyncio.Queue()
        job.subscribers.append(queue)
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue):
        """Unsubscribe from job updates."""
        job = self._jobs.get(job_id)
        if job and queue in job.subscribers:
            job.subscribers.remove(queue)

    async def _notify_subscribers(self, job: Job):
        """Send update to all subscribers."""
        update = ProgressUpdate(
            job_id=job.job_id,
            status=job.status,
            progress=job.progress,
            message=job.message,
            error=job.error,
        )

        for queue in job.subscribers:
            try:
                await queue.put(update)
            except asyncio.QueueFull:
                pass

    def get_job_result(self, job_id: str) -> Optional[JobResult]:
        """Get the result of a completed job."""
        job = self._jobs.get(job_id)
        if not job:
            return None

        return JobResult(
            job_id=job.job_id,
            status=job.status,
            file_path=job.file_path,
            file_name=job.file_name,
            error=job.error,
        )

    def cleanup_job(self, job_id: str):
        """Remove a job from tracking (call after download)."""
        if job_id in self._jobs:
            del self._jobs[job_id]


# Global progress service instance
progress_service = ProgressService()
