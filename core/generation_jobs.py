from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Event, Lock, Thread
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from core.vocabulary_generator import GenerationCancelled, VocabularyGeneratorService
from database.models import GenerationBatch, Template
from database.repositories import DriveSourceFileRepository
from database.session import SessionLocal


TERMINAL_STATUSES = {"ready", "failed", "cancelled"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class GenerationJob:
    id: str
    source_file_id: int
    template_id: int
    name: str
    caption_text: str
    settings_payload: dict[str, Any]
    status: str = "queued"
    batch_id: int | None = None
    batch_name: str | None = None
    total_items: int = 0
    generated_items: int = 0
    percent: int = 0
    error: str | None = None
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    cancel_requested: bool = False
    cancel_event: Event = field(default_factory=Event, repr=False)

    def payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "batch_id": self.batch_id,
            "batch_name": self.batch_name,
            "source_file_id": self.source_file_id,
            "template_id": self.template_id,
            "total_items": self.total_items,
            "generated_items": self.generated_items,
            "percent": self.percent,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "cancel_requested": self.cancel_requested,
        }


class GenerationJobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, GenerationJob] = {}
        self._lock = Lock()

    def start(
        self,
        *,
        source_file_id: int,
        template_id: int,
        name: str,
        caption_text: str,
        settings_payload: dict[str, Any] | None = None,
    ) -> GenerationJob:
        job = GenerationJob(
            id=uuid4().hex,
            source_file_id=source_file_id,
            template_id=template_id,
            name=name,
            caption_text=caption_text,
            settings_payload=settings_payload or {},
        )
        with self._lock:
            self._jobs[job.id] = job

        Thread(target=self._run, args=(job.id,), daemon=True).start()
        return job

    def get(self, job_id: str) -> GenerationJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> GenerationJob | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            if job.status not in TERMINAL_STATUSES:
                job.cancel_requested = True
                job.cancel_event.set()
                job.status = "cancelling"
                job.updated_at = _now()
            return job

    def _update_from_batch(self, job_id: str, batch: GenerationBatch) -> None:
        with self._lock:
            job = self._jobs[job_id]
            total_items = int(batch.total_items or job.total_items or 0)
            generated_items = int(batch.generated_items or 0)
            status = str(batch.status or job.status)
            if job.cancel_requested and status == "generating":
                status = "cancelling"
            job.batch_id = batch.id
            job.batch_name = batch.name
            job.total_items = total_items
            job.generated_items = generated_items
            job.percent = 100 if status == "ready" else round((generated_items / total_items) * 100) if total_items else 0
            job.status = status
            job.updated_at = _now()

    def _mark_failed(self, job_id: str, db: Session, message: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "failed"
            job.error = message
            job.updated_at = _now()
            batch_id = job.batch_id

        if batch_id:
            batch = db.get(GenerationBatch, batch_id)
            if batch:
                batch.status = "failed"
                db.commit()

    def _run(self, job_id: str) -> None:
        db = SessionLocal()
        try:
            with self._lock:
                job = self._jobs[job_id]
                if job.cancel_requested:
                    job.status = "cancelled"
                    job.updated_at = _now()
                    return
                job.status = "generating"
                job.updated_at = _now()

            source = DriveSourceFileRepository(db).get(job.source_file_id)
            template = db.get(Template, job.template_id)
            if not source:
                raise ValueError("Drive CSV source file not found.")
            if not template:
                raise ValueError("Template not found.")

            VocabularyGeneratorService(db).generate_batch(
                source=source,
                template=template,
                name=job.name,
                caption_text=job.caption_text,
                settings_payload=job.settings_payload,
                progress_callback=lambda batch: self._update_from_batch(job_id, batch),
                should_cancel=job.cancel_event.is_set,
            )
        except GenerationCancelled:
            db.rollback()
            with self._lock:
                job = self._jobs[job_id]
                job.status = "cancelled"
                job.percent = round((job.generated_items / job.total_items) * 100) if job.total_items else 0
                job.updated_at = _now()
        except Exception as exc:
            db.rollback()
            self._mark_failed(job_id, db, str(exc))
        finally:
            db.close()
