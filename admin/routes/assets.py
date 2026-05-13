from __future__ import annotations

from flask import Blueprint, send_from_directory
from flask_login import login_required
from sqlalchemy import select

from admin.utils import _json, _no_store
from config.settings import BASE_DIR, get_settings
from database.models import Template
from database.session import SessionLocal
from core.template_storage import ensure_template_files

bp = Blueprint("assets", __name__)


@bp.get("/assets/generated/<path:filename>")
def generated_asset(filename: str):
    return send_from_directory(get_settings().generated_image_dir, filename)


@bp.get("/assets/audio/<path:filename>")
@login_required
def audio_asset(filename: str):
    return send_from_directory(get_settings().generated_audio_dir, filename)


@bp.get("/assets/templates/<path:filename>")
@login_required
def template_asset(filename: str):
    settings = get_settings()
    target = settings.template_config_dir / filename
    if not target.exists():
        db = SessionLocal()
        try:
            template = db.scalar(
                select(Template).where(
                    (Template.image_path.like(f"%/{filename}"))
                    | (Template.config_path.like(f"%/{filename}"))
                )
            )
            if template:
                ensure_template_files(template)
        finally:
            db.close()
    return send_from_directory(settings.template_config_dir, filename)


@bp.get("/")
@bp.get("/<path:path>")
def spa(path: str = ""):
    static_dir = BASE_DIR / "admin" / "static"
    index_file = static_dir / "index.html"
    if index_file.exists():
        if path and (static_dir / path).exists():
            return send_from_directory(static_dir, path)
        return _no_store(send_from_directory(static_dir, "index.html"))
    return _json({"message": "Admin frontend is not built yet. Run `npm run build` in frontend/."})
