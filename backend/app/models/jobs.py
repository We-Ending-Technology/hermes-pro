from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4

class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

@dataclass
class Job:
    job_type: str
    payload: dict
    id: str = field(default_factory=lambda: str(uuid4()))
    status: JobStatus = JobStatus.PENDING
    attempts: int = 0
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class InMemoryJobStore:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}

    def create(self, job_type: str, payload: dict) -> Job:
        job = Job(job_type=job_type, payload=payload)
        self.jobs[job.id] = job
        return job

    def get_pending(self) -> list[Job]:
        return [job for job in self.jobs.values() if job.status in (JobStatus.PENDING, JobStatus.RETRYING)]

    def mark_running(self, job: Job) -> Job:
        job.status = JobStatus.RUNNING
        job.attempts += 1
        return job

    def mark_completed(self, job: Job) -> Job:
        job.status = JobStatus.COMPLETED
        return job

    def mark_failed(self, job: Job, error: str, retry: bool = True) -> Job:
        job.error_message = error
        job.status = JobStatus.RETRYING if retry else JobStatus.FAILED
        return job

job_store = InMemoryJobStore()

class JobProcessor:
    async def process_one(self, job: Job) -> Job:
        job_store.mark_running(job)
        try:
            job_store.mark_completed(job)
        except Exception as exc:
            job_store.mark_failed(job, str(exc))
        return job
