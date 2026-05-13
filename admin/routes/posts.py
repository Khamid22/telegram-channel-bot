from __future__ import annotations

import asyncio
from io import BytesIO

from flask import Blueprint, request, send_file
from flask_login import login_required
from googleapiclient.errors import HttpError
from sqlalchemy import desc, select

from admin.serializers import post_payload, word_payload
from admin.utils import _json, _drive_error_message
from database.models import Post
from database.repositories import PostRepository, WordRepository, analytics_summary
from database.session import SessionLocal
from core.google_drive import GoogleDriveStorage
from core.publishing import PublishingService

bp = Blueprint("posts", __name__)


@bp.get("/api/words")
@login_required
def words():
    db = SessionLocal()
    try:
        limit = int(request.args.get("limit", 100))
        status = request.args.get("status")
        return _json({"items": [word_payload(w) for w in WordRepository(db).list_words(limit, status)]})
    finally:
        db.close()


@bp.get("/api/queue")
@login_required
def queue():
    db = SessionLocal()
    try:
        return _json({"items": [post_payload(p) for p in PostRepository(db).queued(100)]})
    finally:
        db.close()


@bp.post("/api/publish/manual")
@login_required
def publish_manual():
    db = SessionLocal()
    try:
        post = asyncio.run(PublishingService(db).publish_next())
        return _json({"item": post_payload(post)})
    finally:
        db.close()


@bp.post("/api/publish/<int:post_id>")
@login_required
def publish_post(post_id: int):
    db = SessionLocal()
    try:
        post = db.get(Post, post_id)
        if not post:
            return _json({"error": "Post not found"}, 404)
        post = asyncio.run(PublishingService(db).publish(post))
        return _json({"item": post_payload(post)})
    finally:
        db.close()


@bp.get("/api/failed-jobs")
@login_required
def failed_jobs():
    db = SessionLocal()
    try:
        return _json({"items": [post_payload(p) for p in PostRepository(db).failed(100)]})
    finally:
        db.close()


@bp.get("/api/analytics")
@login_required
def analytics():
    db = SessionLocal()
    try:
        return _json(analytics_summary(db))
    finally:
        db.close()


@bp.get("/api/calendar")
@login_required
def calendar():
    db = SessionLocal()
    try:
        posts = db.scalars(select(Post).order_by(desc(Post.scheduled_at)).limit(200)).all()
        return _json({"items": [post_payload(p) for p in posts]})
    finally:
        db.close()


@bp.get("/api/posts/<int:post_id>/image")
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


@bp.get("/api/posts/<int:post_id>/audio")
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
