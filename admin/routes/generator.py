from __future__ import annotations

from flask import Blueprint, request
from flask_login import login_required
from googleapiclient.errors import HttpError
from werkzeug.utils import secure_filename

from admin.serializers import batch_payload, source_payload
from admin.state import generation_jobs
from admin.utils import _json, _drive_error_message
from database.models import Template
from database.repositories import DriveSourceFileRepository, GenerationBatchRepository, VocabularyCollectionRepository
from database.session import SessionLocal
from core.vocabulary_generator import VocabularyGeneratorService

bp = Blueprint("generator", __name__)


@bp.get("/api/generator/vocabulary/batches")
@login_required
def list_batches():
    db = SessionLocal()
    try:
        return _json({"items": [batch_payload(b) for b in GenerationBatchRepository(db).list()]})
    finally:
        db.close()


@bp.post("/api/generator/vocabulary/upload-source")
@login_required
def upload_source():
    source_file = request.files.get("file")
    collection_id = request.form.get("collection_id")
    if not source_file or not collection_id:
        return _json({"error": "Choose a vocabulary folder and CSV file."}, 400)
    if not source_file.filename.lower().endswith(".csv"):
        return _json({"error": "Vocabulary uploads must be CSV files."}, 400)

    db = SessionLocal()
    try:
        collection = VocabularyCollectionRepository(db).get(int(collection_id))
        if not collection:
            return _json({"error": "Vocabulary folder not found. Refresh Drive and try again."}, 404)
        source, rows = VocabularyGeneratorService(db).upload_source(
            collection,
            secure_filename(source_file.filename),
            source_file.read(),
        )
        return _json({"source": source_payload(source), "rows": rows}, 201)
    except (HttpError, RuntimeError, ValueError) as exc:
        return _json({"error": _drive_error_message(exc)}, 400)
    finally:
        db.close()


@bp.get("/api/generator/vocabulary/sources/<int:source_id>/rows")
@login_required
def source_rows(source_id: int):
    db = SessionLocal()
    try:
        source = DriveSourceFileRepository(db).get(source_id)
        if not source:
            return _json({"error": "Drive source file not found."}, 404)
        rows = VocabularyGeneratorService(db).rows_for_source(source)
        return _json({"source": source_payload(source), "rows": rows})
    except (HttpError, RuntimeError, ValueError) as exc:
        return _json({"error": _drive_error_message(exc)}, 400)
    finally:
        db.close()


@bp.post("/api/generator/vocabulary/batches")
@login_required
def create_batch():
    data = request.get_json(force=True)
    db = SessionLocal()
    try:
        source = DriveSourceFileRepository(db).get(int(data.get("source_file_id") or 0))
        template = db.get(Template, int(data.get("template_id") or 0))
        if not source:
            return _json({"error": "Select a Drive CSV source file."}, 400)
        if not template:
            return _json({"error": "Select a saved template."}, 400)
        job = generation_jobs.start(
            source_file_id=source.id,
            template_id=template.id,
            name=data.get("name") or source.name,
            caption_text=data.get("caption_text") or "",
            settings_payload=data.get("settings_payload") or {},
        )
        return _json({"job": job.payload()}, 202)
    except (HttpError, RuntimeError, ValueError) as exc:
        db.rollback()
        return _json({"error": _drive_error_message(exc)}, 400)
    finally:
        db.close()


@bp.get("/api/generator/vocabulary/batches/jobs/<job_id>")
@login_required
def get_job(job_id: str):
    job = generation_jobs.get(job_id)
    if not job:
        return _json({"error": "Generation job not found."}, 404)
    payload: dict = {"job": job.payload()}
    if job.batch_id:
        db = SessionLocal()
        try:
            batch = GenerationBatchRepository(db).get(job.batch_id)
            if batch:
                payload["item"] = batch_payload(batch)
        finally:
            db.close()
    return _json(payload)


@bp.post("/api/generator/vocabulary/batches/jobs/<job_id>/cancel")
@login_required
def cancel_job(job_id: str):
    job = generation_jobs.cancel(job_id)
    if not job:
        return _json({"error": "Generation job not found."}, 404)
    return _json({"job": job.payload()})
