from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

from apscheduler.schedulers.base import STATE_PAUSED, STATE_RUNNING, SchedulerNotRunningError
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from sqlalchemy import desc, select
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename

from config.settings import BASE_DIR, get_settings
from database.models import AdminUser, Post, Schedule, Template, Word
from database.repositories import (
    AdminRepository,
    PostRepository,
    ScheduleRepository,
    TemplateRepository,
    WordRepository,
    analytics_summary,
)
from database.session import SessionLocal
from core.google_sheets import sync_words_from_sheets
from core.scheduler import build_scheduler, normalize_days, normalize_times
from core.image_renderer import VocabularyImageRenderer
from core.publishing import PublishingService, build_caption

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


def _word_payload(word: Word) -> dict[str, Any]:
    return {
        "id": word.id,
        "sheet_id": word.sheet_id,
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
        "image_url": f"/assets/generated/{Path(post.generated_image_path).name}" if post.generated_image_path else None,
        "telegram_message_id": post.telegram_message_id,
        "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "error_message": post.error_message,
        "word": _word_payload(post.word),
        "audio": [
            {
                "id": audio.id,
                "accent": audio.accent.value,
                "url": f"/assets/audio/{Path(audio.file_path).name}",
                "voice": audio.voice,
            }
            for audio in post.word.audio_files
        ],
    }


def _schedule_payload(schedule: Schedule) -> dict[str, Any]:
    return {
        "id": schedule.id,
        "name": schedule.name,
        "timezone": schedule.timezone,
        "days": schedule.days or [],
        "times": schedule.times or [],
        "posts_per_day": schedule.posts_per_day,
        "random_interval_minutes": schedule.random_interval_minutes,
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
        "is_active": template.is_active,
        "created_at": template.created_at.isoformat() if template.created_at else None,
    }


def _schedule_data(data: dict[str, Any], settings) -> dict[str, Any]:
    days = normalize_days(data.get("days") or ["mon", "tue", "wed", "thu", "fri"])
    times = normalize_times(data.get("times") or ["09:00"])
    if not times:
        raise ValueError("At least one valid publish time is required. Use HH:MM, for example 09:00.")

    return {
        "name": data["name"] if "name" in data else None,
        "timezone": data.get("timezone") or settings.timezone,
        "days": days,
        "times": times,
        "posts_per_day": int(data.get("posts_per_day") or len(times)),
        "random_interval_minutes": data.get("random_interval_minutes"),
        "is_active": bool(data.get("is_active", True)),
        "is_paused": bool(data.get("is_paused", False)),
    }


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

    @app.post("/api/sheets/sync")
    @login_required
    def sync_sheets():
        db = SessionLocal()
        try:
            count = sync_words_from_sheets(db)
            return _json({"synced": count})
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

    @app.post("/api/queue/enqueue-next")
    @login_required
    def enqueue_next():
        db = SessionLocal()
        try:
            service = PublishingService(db)
            post = service.ensure_post()
            db.commit()
            return _json({"item": _post_payload(post)}, 201)
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
            schedule = Schedule(
                name=schedule_data["name"],
                timezone=schedule_data["timezone"],
                days=schedule_data["days"],
                times=schedule_data["times"],
                posts_per_day=schedule_data["posts_per_day"],
                random_interval_minutes=schedule_data["random_interval_minutes"],
                is_active=schedule_data["is_active"],
                is_paused=schedule_data["is_paused"],
            )
            db.add(schedule)
            db.commit()
            reload_scheduler()
            return _json({"item": _schedule_payload(schedule)}, 201)
        except ValueError as exc:
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
            if "days" in data:
                data["days"] = normalize_days(data["days"])
            if "times" in data:
                data["times"] = normalize_times(data["times"])
                if not data["times"]:
                    return _json({"error": "At least one valid publish time is required. Use HH:MM, for example 09:00."}, 400)
                if "posts_per_day" not in data:
                    data["posts_per_day"] = len(data["times"])
            for field in ("name", "timezone", "days", "times", "posts_per_day", "random_interval_minutes", "is_active", "is_paused"):
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
            template = Template(
                name=name,
                image_path=str(image_path.relative_to(BASE_DIR)),
                config_path=str(config_path.relative_to(BASE_DIR)),
                is_active=False,
            )
            db.add(template)
            db.commit()
            return _json({"item": _template_payload(template)}, 201)
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
            return _json({"image_url": f"/assets/generated/{path.name}", "caption": build_caption(preview_word)})
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
