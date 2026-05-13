from __future__ import annotations

import asyncio
from datetime import date, datetime, time, timedelta
import html
from io import BytesIO
import json
import re
import secrets
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.base import STATE_PAUSED, STATE_RUNNING, SchedulerNotRunningError
from flask import Flask, jsonify, redirect, request, send_file, send_from_directory, session as flask_session, url_for
from flask_cors import CORS
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request as GoogleAuthRequest
from googleapiclient.discovery import build as build_google_service
from googleapiclient.errors import HttpError
from sqlalchemy import desc, select
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from config.settings import BASE_DIR, get_settings
from database.models import AdminUser, DriveSourceFile, GenerationBatch, Post, Schedule, Template, VocabularyCollection, Word
from database.repositories import (
    AdminRepository,
    DriveSourceFileRepository,
    GenerationBatchRepository,
    GoogleDriveCredentialRepository,
    PostRepository,
    ScheduleRepository,
    TemplateRepository,
    VocabularyCollectionRepository,
    WordRepository,
    analytics_summary,
)
from database.session import SessionLocal
from core.google_drive import GoogleDriveStorage
from core.google_drive_auth import build_authorization_url, credentials_from_refresh_token, exchange_code_for_tokens
from core.scheduler import build_scheduler, normalize_time, normalize_times
from core.image_renderer import VocabularyImageRenderer
from core.publishing import PublishingService, build_caption
from core.template_storage import ensure_template_files
from core.vocabulary_generator import VocabularyGeneratorService

login_manager = LoginManager()
runtime_scheduler = None


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value.lower()).strip("-") or "template"


def _json(data: Any, status: int = 200):
    return jsonify(data), status


def _no_store(response):
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


def _drive_error_message(exc: Exception) -> str:
    if isinstance(exc, HttpError):
        try:
            payload = json.loads(exc.content.decode("utf-8"))
            detail = payload.get("error", {}).get("message")
            if detail:
                return detail
        except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
            pass
    return str(exc)


def _html_message(title: str, message: str, status: int = 200):
    escaped_title = html.escape(title)
    escaped_message = html.escape(message)
    return (
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 48px; color: #172033; }}
    a {{ color: #2357d9; }}
  </style>
</head>
<body>
  <h1>{escaped_title}</h1>
  <p>{escaped_message}</p>
  <p><a href="/">Return to admin</a></p>
</body>
</html>""",
        status,
        {"Content-Type": "text/html; charset=utf-8"},
    )


def _word_payload(word: Word) -> dict[str, Any]:
    return {
        "id": word.id,
        "source_file_id": word.source_file_id,
        "source_index": word.source_index,
        "word": word.word,
        "word_type": word.word_type,
        "phonetic": word.phonetic,
        "definition": word.definition,
        "example": word.example,
        "level": word.level,
        "accent": word.accent,
        "status": word.status.value,
        "created_at": word.created_at.isoformat() if word.created_at else None,
    }


def _post_payload(post: Post) -> dict[str, Any]:
    return {
        "id": post.id,
        "status": post.status.value,
        "caption": post.caption,
        "generated_image_path": post.generated_image_path,
        "image_url": f"/api/posts/{post.id}/image" if post.image_drive_file_id else None,
        "telegram_message_id": post.telegram_message_id,
        "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "error_message": post.error_message,
        "word": _word_payload(post.word),
        "audio": [{"id": f"post-{post.id}", "url": f"/api/posts/{post.id}/audio", "voice": "multilevel essays"}] if post.audio_drive_file_id else [],
        "batch": _batch_payload(post.batch) if post.batch else None,
    }


def _schedule_payload(schedule: Schedule) -> dict[str, Any]:
    return {
        "id": schedule.id,
        "name": schedule.name,
        "content_type": schedule.content_type,
        "batch_id": schedule.batch_id,
        "batch_name": schedule.batch.name if schedule.batch else None,
        "timezone": schedule.timezone,
        "start_date": schedule.start_date.isoformat() if schedule.start_date else None,
        "end_date": schedule.end_date.isoformat() if schedule.end_date else None,
        "dispatch_mode": schedule.dispatch_mode,
        "window_start": schedule.window_start,
        "window_end": schedule.window_end,
        "manual_times": schedule.manual_times or [],
        "posts_per_day": schedule.posts_per_day,
        "scheduled_post_count": schedule.scheduled_post_count,
        "is_active": schedule.is_active,
        "is_paused": schedule.is_paused,
    }


def _template_payload(template: Template) -> dict[str, Any]:
    return {
        "id": template.id,
        "name": template.name,
        "image_path": template.image_path,
        "config_path": template.config_path,
        "image_url": f"/assets/templates/{Path(template.image_path).name}",
        "drive_backed": bool(template.image_drive_file_id and template.config_drive_file_id),
        "is_active": template.is_active,
        "created_at": template.created_at.isoformat() if template.created_at else None,
    }


def _collection_payload(collection: VocabularyCollection) -> dict[str, Any]:
    return {
        "id": collection.id,
        "name": collection.name,
        "slug": collection.slug,
        "drive_folder_id": collection.drive_folder_id,
        "source_folder_id": collection.source_folder_id,
        "generated_folder_id": collection.generated_folder_id,
    }


def _source_payload(source: DriveSourceFile) -> dict[str, Any]:
    return {
        "id": source.id,
        "collection_id": source.collection_id,
        "collection_name": source.collection.name if source.collection else None,
        "drive_file_id": source.drive_file_id,
        "name": source.name,
        "mime_type": source.mime_type,
        "row_count": source.row_count,
        "updated_at": source.updated_at.isoformat() if source.updated_at else None,
    }


def _batch_payload(batch: GenerationBatch) -> dict[str, Any]:
    return {
        "id": batch.id,
        "name": batch.name,
        "status": batch.status,
        "collection_id": batch.collection_id,
        "collection_name": batch.collection.name if batch.collection else None,
        "source_file_id": batch.source_file_id,
        "source_file_name": batch.source_file.name if batch.source_file else None,
        "template_id": batch.template_id,
        "template_name": batch.template.name if batch.template else None,
        "caption_text": batch.caption_text,
        "total_items": batch.total_items,
        "generated_items": batch.generated_items,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
    }


def _schedule_data(data: dict[str, Any], settings) -> dict[str, Any]:
    if not data.get("batch_id"):
        raise ValueError("Select a generated vocabulary batch.")
    start_date = date.fromisoformat(data["start_date"])
    end_date = date.fromisoformat(data["end_date"])
    if end_date < start_date:
        raise ValueError("End date must be on or after the start date.")

    dispatch_mode = data.get("dispatch_mode") or "even"
    manual_times = normalize_times(data.get("manual_times") or [])
    window_start = normalize_time(data.get("window_start") or "09:00")
    window_end = normalize_time(data.get("window_end") or "18:00")
    posts_per_day = int(data.get("posts_per_day") or 1)
    if posts_per_day < 1:
        raise ValueError("Posts per day must be at least 1.")
    if dispatch_mode == "manual":
        if not manual_times:
            raise ValueError("Manual scheduling requires at least one time.")
        posts_per_day = len(manual_times)
    else:
        if not window_start or not window_end:
            raise ValueError("Even scheduling requires a valid start and end time.")
        start_minutes = int(window_start[:2]) * 60 + int(window_start[3:])
        end_minutes = int(window_end[:2]) * 60 + int(window_end[3:])
        if end_minutes < start_minutes:
            raise ValueError("The time window end must be after the start.")

    return {
        "name": data["name"] if "name" in data else None,
        "content_type": "vocabulary",
        "batch_id": int(data["batch_id"]),
        "timezone": data.get("timezone") or settings.timezone,
        "start_date": start_date,
        "end_date": end_date,
        "dispatch_mode": dispatch_mode,
        "window_start": window_start,
        "window_end": window_end,
        "manual_times": manual_times,
        "posts_per_day": posts_per_day,
        "is_active": bool(data.get("is_active", True)),
        "is_paused": bool(data.get("is_paused", False)),
    }


def _times_for_schedule(schedule_data: dict[str, Any]) -> list[str]:
    if schedule_data["dispatch_mode"] == "manual":
        return schedule_data["manual_times"]

    posts_per_day = schedule_data["posts_per_day"]
    start = schedule_data["window_start"]
    end = schedule_data["window_end"]
    start_minutes = int(start[:2]) * 60 + int(start[3:])
    end_minutes = int(end[:2]) * 60 + int(end[3:])
    if posts_per_day == 1:
        return [start]

    step = (end_minutes - start_minutes) / (posts_per_day - 1)
    publish_times = []
    for index in range(posts_per_day):
        minute_value = round(start_minutes + step * index)
        publish_times.append(f"{minute_value // 60:02d}:{minute_value % 60:02d}")
    return publish_times


def _schedule_slots(schedule_data: dict[str, Any]) -> list[datetime]:
    zone = ZoneInfo(schedule_data["timezone"])
    slots: list[datetime] = []
    current_day = schedule_data["start_date"]
    while current_day <= schedule_data["end_date"]:
        for publish_time in _times_for_schedule(schedule_data):
            hour, minute = [int(part) for part in publish_time.split(":", 1)]
            slots.append(datetime.combine(current_day, time(hour, minute), tzinfo=zone))
        current_day += timedelta(days=1)
    return slots


def _scheduler_state() -> str:
    if not runtime_scheduler:
        return "stopped"
    if runtime_scheduler.state == STATE_RUNNING:
        return "running"
    if runtime_scheduler.state == STATE_PAUSED:
        return "paused"
    return "stopped"


def _shutdown_scheduler() -> None:
    global runtime_scheduler
    if not runtime_scheduler:
        return
    try:
        runtime_scheduler.shutdown(wait=False)
    except SchedulerNotRunningError:
        pass
    finally:
        runtime_scheduler = None


def reload_scheduler() -> None:
    global runtime_scheduler
    _shutdown_scheduler()
    runtime_scheduler = build_scheduler()
    runtime_scheduler.start()


def ensure_scheduler_running():
    global runtime_scheduler
    if runtime_scheduler and runtime_scheduler.state in (STATE_RUNNING, STATE_PAUSED):
        return runtime_scheduler
    runtime_scheduler = build_scheduler()
    runtime_scheduler.start()
    return runtime_scheduler


@login_manager.user_loader
def load_user(user_id: str):
    db = SessionLocal()
    try:
        return AdminRepository(db).by_id(int(user_id))
    finally:
        db.close()


def create_app(start_background_scheduler: bool = False) -> Flask:
    settings = get_settings()
    static_dir = BASE_DIR / "admin" / "static"
    app = Flask(__name__, static_folder=str(static_dir), static_url_path="")
    app.secret_key = settings.secret_key
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    CORS(app, supports_credentials=True)
    login_manager.init_app(app)

    if start_background_scheduler:
        reload_scheduler()

    @app.get("/api/health")
    def health():
        return _json({"ok": True})

    @app.post("/api/auth/login")
    def login():
        data = request.get_json(force=True)
        username = data.get("username", "")
        password = data.get("password", "")
        db = SessionLocal()
        try:
            user = AdminRepository(db).by_username(username)
            if not user or not check_password_hash(user.password_hash, password):
                return _json({"error": "Invalid username or password"}, 401)
            login_user(user)
            return _json({"user": {"id": user.id, "username": user.username}})
        finally:
            db.close()

    @app.post("/api/auth/logout")
    @login_required
    def logout():
        logout_user()
        return _json({"ok": True})

    @app.get("/api/me")
    def me():
        if not current_user.is_authenticated:
            return _json({"user": None}, 401)
        return _json({"user": {"id": current_user.id, "username": current_user.username}})

    def google_drive_redirect_uri() -> str:
        scheme = request.headers.get("X-Forwarded-Proto", request.scheme)
        return url_for("google_drive_oauth_callback", _external=True, _scheme=scheme)

    @app.get("/api/drive/oauth/status")
    @login_required
    def google_drive_oauth_status():
        db = SessionLocal()
        try:
            credential = GoogleDriveCredentialRepository(db).active()
            configured = bool(settings.google_oauth_client_id and settings.google_oauth_client_secret)
            return _json(
                {
                    "configured": configured,
                    "connected": bool(credential),
                    "account_email": credential.account_email if credential else None,
                    "redirect_uri": google_drive_redirect_uri(),
                    "root_folder_name": settings.google_drive_root_folder_name,
                    "root_folder_id": settings.google_drive_root_folder_id or None,
                }
            )
        finally:
            db.close()

    @app.post("/api/drive/oauth/start")
    @login_required
    def google_drive_oauth_start():
        if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
            return _json({"error": "Configure GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET first."}, 400)
        state = secrets.token_urlsafe(32)
        flask_session["google_drive_oauth_state"] = state
        redirect_uri = google_drive_redirect_uri()
        return _json(
            {
                "authorization_url": build_authorization_url(
                    client_id=settings.google_oauth_client_id,
                    redirect_uri=redirect_uri,
                    state=state,
                ),
                "redirect_uri": redirect_uri,
            }
        )

    @app.get("/api/drive/oauth/callback")
    @login_required
    def google_drive_oauth_callback():
        if request.args.get("error"):
            return _html_message("Google Drive Not Connected", request.args.get("error_description") or request.args["error"], 400)

        expected_state = flask_session.pop("google_drive_oauth_state", None)
        if not expected_state or request.args.get("state") != expected_state:
            return _html_message("Google Drive Not Connected", "The authorization state did not match. Start the connection again.", 400)

        code = request.args.get("code")
        if not code:
            return _html_message("Google Drive Not Connected", "Google did not return an authorization code.", 400)

        db = SessionLocal()
        try:
            redirect_uri = google_drive_redirect_uri()
            tokens = exchange_code_for_tokens(
                client_id=settings.google_oauth_client_id,
                client_secret=settings.google_oauth_client_secret,
                redirect_uri=redirect_uri,
                code=code,
            )
            credential_repo = GoogleDriveCredentialRepository(db)
            existing = credential_repo.active()
            refresh_token = tokens.get("refresh_token") or (existing.refresh_token if existing else None)
            if not refresh_token:
                return _html_message(
                    "Google Drive Not Connected",
                    "Google did not return a refresh token. Start the connection again and approve offline access.",
                    400,
                )

            credentials = credentials_from_refresh_token(
                client_id=settings.google_oauth_client_id,
                client_secret=settings.google_oauth_client_secret,
                refresh_token=refresh_token,
            )
            credentials.refresh(GoogleAuthRequest())
            about = build_google_service("drive", "v3", credentials=credentials, cache_discovery=False).about().get(
                fields="user(emailAddress,displayName)"
            ).execute()
            user = about.get("user", {})
            credential_repo.save(
                refresh_token=refresh_token,
                account_email=user.get("emailAddress") or user.get("displayName"),
                scopes=tokens.get("scope"),
            )
            db.commit()
        except (RuntimeError, RefreshError, HttpError) as exc:
            db.rollback()
            return _html_message("Google Drive Not Connected", _drive_error_message(exc), 400)
        finally:
            db.close()

        return redirect("/#dashboard")

    @app.get("/api/drive/vocabulary")
    @login_required
    def drive_vocabulary_catalog():
        db = SessionLocal()
        try:
            return _json(
                {
                    "collections": [_collection_payload(item) for item in VocabularyCollectionRepository(db).list()],
                    "sources": [_source_payload(item) for item in DriveSourceFileRepository(db).list()],
                }
            )
        finally:
            db.close()

    @app.post("/api/drive/refresh")
    @login_required
    def refresh_drive():
        db = SessionLocal()
        try:
            payload = VocabularyGeneratorService(db).refresh_drive_catalog()
            return _json(
                {
                    "collections": [_collection_payload(item) for item in payload["collections"]],
                    "sources": [_source_payload(item) for item in payload["sources"]],
                }
            )
        except (HttpError, RuntimeError) as exc:
            return _json({"error": _drive_error_message(exc)}, 400)
        finally:
            db.close()

    @app.get("/api/words")
    @login_required
    def words():
        db = SessionLocal()
        try:
            limit = int(request.args.get("limit", 100))
            status = request.args.get("status")
            return _json({"items": [_word_payload(word) for word in WordRepository(db).list_words(limit, status)]})
        finally:
            db.close()

    @app.get("/api/queue")
    @login_required
    def queue():
        db = SessionLocal()
        try:
            return _json({"items": [_post_payload(post) for post in PostRepository(db).queued(100)]})
        finally:
            db.close()

    @app.post("/api/publish/manual")
    @login_required
    def publish_manual():
        db = SessionLocal()
        try:
            post = asyncio.run(PublishingService(db).publish_next())
            return _json({"item": _post_payload(post)})
        finally:
            db.close()

    @app.post("/api/publish/<int:post_id>")
    @login_required
    def publish_post(post_id: int):
        db = SessionLocal()
        try:
            post = db.get(Post, post_id)
            if not post:
                return _json({"error": "Post not found"}, 404)
            post = asyncio.run(PublishingService(db).publish(post))
            return _json({"item": _post_payload(post)})
        finally:
            db.close()

    @app.get("/api/failed-jobs")
    @login_required
    def failed_jobs():
        db = SessionLocal()
        try:
            return _json({"items": [_post_payload(post) for post in PostRepository(db).failed(100)]})
        finally:
            db.close()

    @app.get("/api/analytics")
    @login_required
    def analytics():
        db = SessionLocal()
        try:
            return _json(analytics_summary(db))
        finally:
            db.close()

    @app.get("/api/calendar")
    @login_required
    def calendar():
        db = SessionLocal()
        try:
            posts = db.scalars(select(Post).order_by(desc(Post.scheduled_at)).limit(200)).all()
            return _json({"items": [_post_payload(post) for post in posts]})
        finally:
            db.close()

    @app.get("/api/schedules")
    @login_required
    def list_schedules():
        db = SessionLocal()
        try:
            return _json({"items": [_schedule_payload(schedule) for schedule in ScheduleRepository(db).list()]})
        finally:
            db.close()

    @app.post("/api/schedules")
    @login_required
    def create_schedule():
        data = request.get_json(force=True)
        db = SessionLocal()
        try:
            schedule_data = _schedule_data(data, settings)
            batch = GenerationBatchRepository(db).get(schedule_data["batch_id"])
            if not batch or batch.status != "ready":
                return _json({"error": "Select a ready generated batch."}, 400)
            slots = _schedule_slots(schedule_data)
            posts = PostRepository(db).unscheduled_for_batch(batch.id, limit=len(slots))
            if not posts:
                return _json({"error": "This batch has no unscheduled posts left."}, 400)
            schedule = Schedule(
                name=schedule_data["name"],
                content_type=schedule_data["content_type"],
                batch=batch,
                timezone=schedule_data["timezone"],
                start_date=schedule_data["start_date"],
                end_date=schedule_data["end_date"],
                dispatch_mode=schedule_data["dispatch_mode"],
                window_start=schedule_data["window_start"],
                window_end=schedule_data["window_end"],
                manual_times=schedule_data["manual_times"],
                posts_per_day=schedule_data["posts_per_day"],
                is_active=schedule_data["is_active"],
                is_paused=schedule_data["is_paused"],
            )
            db.add(schedule)
            db.flush()
            for post, scheduled_at in zip(posts, slots):
                post.schedule = schedule
                post.scheduled_at = scheduled_at
            schedule.scheduled_post_count = len(posts)
            db.commit()
            reload_scheduler()
            return _json({"item": _schedule_payload(schedule)}, 201)
        except (RuntimeError, ValueError) as exc:
            db.rollback()
            return _json({"error": str(exc)}, 400)
        finally:
            db.close()

    @app.patch("/api/schedules/<int:schedule_id>")
    @login_required
    def update_schedule(schedule_id: int):
        data = request.get_json(force=True)
        db = SessionLocal()
        try:
            schedule = db.get(Schedule, schedule_id)
            if not schedule:
                return _json({"error": "Schedule not found"}, 404)
            for field in ("name", "is_active", "is_paused"):
                if field in data:
                    setattr(schedule, field, data[field])
            db.commit()
            reload_scheduler()
            return _json({"item": _schedule_payload(schedule)})
        finally:
            db.close()

    @app.delete("/api/schedules/<int:schedule_id>")
    @login_required
    def delete_schedule(schedule_id: int):
        db = SessionLocal()
        try:
            schedule = db.get(Schedule, schedule_id)
            if not schedule:
                return _json({"error": "Schedule not found"}, 404)
            for post in schedule.posts:
                if post.published_at is None:
                    post.schedule = None
                    post.scheduled_at = None
            db.delete(schedule)
            db.commit()
            reload_scheduler()
            return _json({"ok": True})
        finally:
            db.close()

    @app.post("/api/scheduler/pause")
    @login_required
    def pause_scheduler():
        scheduler = ensure_scheduler_running()
        if scheduler.state != STATE_PAUSED:
            scheduler.pause()
        return _json({"paused": True, "state": _scheduler_state()})

    @app.post("/api/scheduler/resume")
    @login_required
    def resume_scheduler():
        scheduler = ensure_scheduler_running()
        if scheduler.state == STATE_PAUSED:
            scheduler.resume()
        return _json({"paused": False, "state": _scheduler_state()})

    @app.get("/api/templates")
    @login_required
    def templates():
        db = SessionLocal()
        try:
            return _json({"items": [_template_payload(template) for template in TemplateRepository(db).list()]})
        finally:
            db.close()

    @app.get("/api/generator/vocabulary/batches")
    @login_required
    def vocabulary_batches():
        db = SessionLocal()
        try:
            return _json({"items": [_batch_payload(batch) for batch in GenerationBatchRepository(db).list()]})
        finally:
            db.close()

    @app.post("/api/generator/vocabulary/upload-source")
    @login_required
    def upload_vocabulary_source():
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
            return _json({"source": _source_payload(source), "rows": rows}, 201)
        except (HttpError, RuntimeError, ValueError) as exc:
            return _json({"error": _drive_error_message(exc)}, 400)
        finally:
            db.close()

    @app.get("/api/generator/vocabulary/sources/<int:source_id>/rows")
    @login_required
    def vocabulary_source_rows(source_id: int):
        db = SessionLocal()
        try:
            source = DriveSourceFileRepository(db).get(source_id)
            if not source:
                return _json({"error": "Drive source file not found."}, 404)
            rows = VocabularyGeneratorService(db).rows_for_source(source)
            return _json({"source": _source_payload(source), "rows": rows})
        except (HttpError, RuntimeError, ValueError) as exc:
            return _json({"error": _drive_error_message(exc)}, 400)
        finally:
            db.close()

    @app.post("/api/generator/vocabulary/batches")
    @login_required
    def create_vocabulary_batch():
        data = request.get_json(force=True)
        db = SessionLocal()
        try:
            source = DriveSourceFileRepository(db).get(int(data.get("source_file_id") or 0))
            template = db.get(Template, int(data.get("template_id") or 0))
            if not source:
                return _json({"error": "Select a Drive CSV source file."}, 400)
            if not template:
                return _json({"error": "Select a saved template."}, 400)
            batch = VocabularyGeneratorService(db).generate_batch(
                source=source,
                template=template,
                name=data.get("name") or source.name,
                caption_text=data.get("caption_text") or "",
                settings_payload=data.get("settings_payload") or {},
            )
            return _json({"item": _batch_payload(batch)}, 201)
        except (HttpError, RuntimeError, ValueError) as exc:
            db.rollback()
            return _json({"error": _drive_error_message(exc)}, 400)
        finally:
            db.close()

    @app.post("/api/templates")
    @login_required
    def upload_template():
        name = request.form.get("name") or "Custom Template"
        image = request.files.get("image")
        config_file = request.files.get("config")
        if not image:
            return _json({"error": "Template image is required"}, 400)

        slug = _slug(name)
        template_dir = settings.template_config_dir
        template_dir.mkdir(parents=True, exist_ok=True)
        image_filename = secure_filename(f"{slug}-{image.filename}")
        image_path = template_dir / image_filename
        image.save(image_path)

        if config_file:
            config_filename = secure_filename(f"{slug}-{config_file.filename}")
            config_path = template_dir / config_filename
            config_file.save(config_path)
        else:
            default_config = json.loads((template_dir / "default.json").read_text(encoding="utf-8"))
            default_config["background_image"] = str(image_path.relative_to(BASE_DIR))
            config_path = template_dir / f"{slug}.json"
            config_path.write_text(json.dumps(default_config, indent=2), encoding="utf-8")

        db = SessionLocal()
        try:
            drive = GoogleDriveStorage()
            drive_structure = drive.ensure_root_structure()
            image_drive = drive.upload_file(
                image_path,
                name=image_path.name,
                parent_id=str(drive_structure["templates_id"]),
                mime_type=image.mimetype or "image/png",
            )
            config_drive = drive.upload_file(
                config_path,
                name=config_path.name,
                parent_id=str(drive_structure["templates_id"]),
                mime_type="application/json",
            )
            template = Template(
                name=name,
                image_path=str(image_path.relative_to(BASE_DIR)),
                config_path=str(config_path.relative_to(BASE_DIR)),
                image_drive_file_id=image_drive.id,
                config_drive_file_id=config_drive.id,
                is_active=False,
            )
            db.add(template)
            db.commit()
            return _json({"item": _template_payload(template)}, 201)
        except (HttpError, RuntimeError) as exc:
            db.rollback()
            return _json({"error": _drive_error_message(exc)}, 400)
        finally:
            db.close()

    @app.post("/api/templates/<int:template_id>/activate")
    @login_required
    def activate_template(template_id: int):
        db = SessionLocal()
        try:
            template = TemplateRepository(db).set_active(template_id)
            db.commit()
            return _json({"item": _template_payload(template)})
        finally:
            db.close()

    @app.post("/api/templates/<int:template_id>/preview")
    @login_required
    def preview_template(template_id: int):
        data = request.get_json(silent=True) or {}
        db = SessionLocal()
        try:
            template = db.get(Template, template_id)
            if not template:
                return _json({"error": "Template not found"}, 404)
            ensure_template_files(template)
            preview_payload = {
                "word": data.get("word", "serendipity"),
                "word_type": data.get("word_type", "noun"),
                "phonetic": data.get("phonetic", "/ˌser.ənˈdɪp.ə.ti/"),
                "definition": data.get("definition", "The chance discovery of something valuable or pleasant."),
                "example": data.get("example", "Finding that book in the tiny shop was pure serendipity."),
                "level": data.get("level", "C1"),
            }
            path = VocabularyImageRenderer(template.config_path).preview(preview_payload, template.config_path)
            preview_word = type("PreviewWord", (), preview_payload)()
            return _json({"image_url": f"/assets/generated/{path.name}", "caption": build_caption(preview_word, data.get("caption_text"))})
        except (HttpError, RuntimeError) as exc:
            return _json({"error": _drive_error_message(exc)}, 400)
        finally:
            db.close()

    @app.post("/api/fonts")
    @login_required
    def upload_font():
        font = request.files.get("font")
        if not font:
            return _json({"error": "Font file is required"}, 400)
        filename = secure_filename(font.filename)
        path = settings.assets_dir / "fonts" / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        font.save(path)
        return _json({"path": str(path.relative_to(BASE_DIR))}, 201)

    @app.get("/api/posts/<int:post_id>/image")
    @login_required
    def post_image(post_id: int):
        db = SessionLocal()
        try:
            post = db.get(Post, post_id)
            if not post or not post.image_drive_file_id:
                return _json({"error": "Generated image not found."}, 404)
            data = GoogleDriveStorage().download_bytes(post.image_drive_file_id)
            return send_file(BytesIO(data), mimetype="image/png", download_name=f"post-{post.id}.png")
        except (HttpError, RuntimeError) as exc:
            return _json({"error": _drive_error_message(exc)}, 400)
        finally:
            db.close()

    @app.get("/api/posts/<int:post_id>/audio")
    @login_required
    def post_audio(post_id: int):
        db = SessionLocal()
        try:
            post = db.get(Post, post_id)
            if not post or not post.audio_drive_file_id:
                return _json({"error": "Generated audio not found."}, 404)
            data = GoogleDriveStorage().download_bytes(post.audio_drive_file_id)
            return send_file(BytesIO(data), mimetype="audio/mpeg", download_name=f"post-{post.id}.mp3")
        except (HttpError, RuntimeError) as exc:
            return _json({"error": _drive_error_message(exc)}, 400)
        finally:
            db.close()

    @app.get("/assets/generated/<path:filename>")
    def generated_asset(filename: str):
        return send_from_directory(settings.generated_image_dir, filename)

    @app.get("/assets/audio/<path:filename>")
    @login_required
    def audio_asset(filename: str):
        return send_from_directory(settings.generated_audio_dir, filename)

    @app.get("/assets/templates/<path:filename>")
    @login_required
    def template_asset(filename: str):
        target = settings.template_config_dir / filename
        if not target.exists():
            db = SessionLocal()
            try:
                template = db.scalar(
                    select(Template).where(
                        (Template.image_path.like(f"%/{filename}")) | (Template.config_path.like(f"%/{filename}"))
                    )
                )
                if template:
                    ensure_template_files(template)
            finally:
                db.close()
        return send_from_directory(settings.template_config_dir, filename)

    @app.get("/")
    @app.get("/<path:path>")
    def index(path: str = ""):
        index_file = static_dir / "index.html"
        if index_file.exists():
            if path and (static_dir / path).exists():
                return send_from_directory(static_dir, path)
            return _no_store(send_from_directory(static_dir, "index.html"))
        return _json({"message": "Admin frontend is not built yet. Run `npm run build` in frontend/."})

    return app
