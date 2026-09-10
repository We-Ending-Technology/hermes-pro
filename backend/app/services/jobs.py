from typing import Any
from ..models.jobs import Job, JobStatus

ALLOWED_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.PENDING: {JobStatus.RUNNING, JobStatus.FAILED, JobStatus.RETRYING},
    JobStatus.RUNNING: {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.RETRYING},
    JobStatus.RETRYING: {JobStatus.RUNNING, JobStatus.FAILED},
    JobStatus.COMPLETED: set(),
    JobStatus.FAILED: set(),
}

class JobService:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.idempotency: dict[str, str] = {}

    def create(self, job_type: str, payload: dict[str, Any], idempotency_key: str | None = None) -> Job:
        if idempotency_key and idempotency_key in self.idempotency:
            return self.jobs[self.idempotency[idempotency_key]]
        job = Job(job_type=job_type, payload=payload)
        self.jobs[job.id] = job
        if idempotency_key:
            self.idempotency[idempotency_key] = job.id
        return job

    def get(self, job_id: str) -> Job:
        if job_id not in self.jobs:
            raise KeyError(job_id)
        return self.jobs[job_id]

    def transition(self, job_id: str, status: JobStatus, error_message: str | None = None) -> Job:
        job = self.get(job_id)
        if status != job.status and status not in ALLOWED_TRANSITIONS[job.status]:
            raise ValueError(f"invalid transition: {job.status} -> {status}")
        job.status = status
        job.error_message = error_message
        if status in (JobStatus.RUNNING, JobStatus.RETRYING):
            job.attempts += 1 if status == JobStatus.RUNNING else 0
        return job

    def list(self) -> list[Job]:
        return list(self.jobs.values())

job_service = JobService()
