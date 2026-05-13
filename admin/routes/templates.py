from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from flask import Blueprint, request
from flask_login import login_required
from googleapiclient.errors import HttpError
from PIL import Image
from werkzeug.utils import secure_filename

from admin.serializers import template_payload
from admin.utils import _json, _drive_error_message
from config.settings import BASE_DIR, get_settings
from database.models import Template
from database.repositories import TemplateRepository
from database.session import SessionLocal
from core.google_drive import GoogleDriveStorage
from core.image_renderer import VocabularyImageRenderer
from core.publishing import build_caption
from core.template_storage import ensure_template_files

bp = Blueprint("templates", __name__)


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value.lower()).strip("-") or "template"


def _auto_config(image_path: Path) -> dict[str, Any]:
    """Generate a default template config from an image's dimensions."""
    with Image.open(image_path) as img:
        width, height = img.size
    left = max(48, round(width * 0.14))
    content_width = max(320, width - (left * 2))
    return {
        "name": image_path.stem.replace("-", " ").title(),
        "background_image": str(image_path.relative_to(BASE_DIR)),
        "fields": {
            "word": {
                "x": left, "y": round(height * 0.22), "width": content_width,
                "font_path": "assets/fonts/Georgia-Bold.ttf",
                "font_size": max(48, round(height * 0.075)),
                "min_font_size": max(28, round(height * 0.04)),
                "color": "#0D0D0D", "line_spacing": 12, "max_lines": 1,
            },
            "word_type": {
                "x": left, "y": round(height * 0.34), "width": content_width,
                "font_path": "assets/fonts/Georgia.ttf",
                "font_size": max(32, round(height * 0.045)),
                "min_font_size": max(22, round(height * 0.03)),
                "color": "#0D0D0D", "line_spacing": 8, "max_lines": 1,
            },
            "definition": {
                "x": left, "y": round(height * 0.5), "width": content_width,
                "font_path": "assets/fonts/Georgia.ttf",
                "font_size": max(34, round(height * 0.045)),
                "min_font_size": max(24, round(height * 0.03)),
                "color": "#0D0D0D", "line_spacing": 18, "max_lines": 4,
                "prefix": "Definition: ",
            },
            "example": {
                "x": left, "y": round(height * 0.74), "width": content_width,
                "font_path": "assets/fonts/Georgia.ttf",
                "font_size": max(30, round(height * 0.04)),
                "min_font_size": max(22, round(height * 0.028)),
                "color": "#0D0D0D", "line_spacing": 18, "max_lines": 4,
                "prefix": "Example: \"", "suffix": "\"",
            },
        },
    }


@bp.get("/api/templates")
@login_required
def list_templates():
    db = SessionLocal()
    try:
        return _json({"items": [template_payload(t) for t in TemplateRepository(db).list()]})
    finally:
        db.close()


@bp.post("/api/templates")
@login_required
def upload_template():
    settings = get_settings()
    name = request.form.get("name") or "Custom Template"
    image = request.files.get("image")
    config_file = request.files.get("config")
    if not image:
        return _json({"error": "Template image is required"}, 400)

    slug = _slug(name)
    template_dir = settings.template_config_dir
    template_dir.mkdir(parents=True, exist_ok=True)

    image_path = template_dir / secure_filename(f"{slug}-{image.filename}")
    image.save(image_path)

    if config_file:
        config_path = template_dir / secure_filename(f"{slug}-{config_file.filename}")
        config_file.save(config_path)
    else:
        config_path = template_dir / f"{slug}.json"
        config_path.write_text(json.dumps(_auto_config(image_path), indent=2), encoding="utf-8")

    db = SessionLocal()
    try:
        drive = GoogleDriveStorage()
        structure = drive.ensure_root_structure()
        image_drive = drive.upload_file(
            image_path, name=image_path.name,
            parent_id=str(structure["templates_id"]),
            mime_type=image.mimetype or "image/png",
        )
        config_drive = drive.upload_file(
            config_path, name=config_path.name,
            parent_id=str(structure["templates_id"]),
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
        return _json({"item": template_payload(template)}, 201)
    except (HttpError, RuntimeError) as exc:
        db.rollback()
        return _json({"error": _drive_error_message(exc)}, 400)
    finally:
        db.close()


@bp.post("/api/templates/<int:template_id>/activate")
@login_required
def activate_template(template_id: int):
    db = SessionLocal()
    try:
        template = TemplateRepository(db).set_active(template_id)
        db.commit()
        return _json({"item": template_payload(template)})
    finally:
        db.close()


@bp.post("/api/templates/<int:template_id>/preview")
@login_required
def preview_template(template_id: int):
    data = request.get_json(silent=True) or {}
    db = SessionLocal()
    try:
        template = db.get(Template, template_id)
        if not template:
            return _json({"error": "Template not found"}, 404)
        ensure_template_files(template)
        preview_data = {
            "word": data.get("word", "serendipity"),
            "word_type": data.get("word_type", "noun"),
            "phonetic": data.get("phonetic", "/ˌser.ənˈdɪp.ə.ti/"),
            "definition": data.get("definition", "The chance discovery of something valuable or pleasant."),
            "example": data.get("example", "Finding that book in the tiny shop was pure serendipity."),
            "level": data.get("level", "C1"),
        }
        path = VocabularyImageRenderer(template.config_path).preview(preview_data, template.config_path)
        preview_word = type("PreviewWord", (), preview_data)()
        return _json({
            "image_url": f"/assets/generated/{path.name}",
            "caption": build_caption(preview_word, data.get("caption_text")),
        })
    except (HttpError, RuntimeError) as exc:
        return _json({"error": _drive_error_message(exc)}, 400)
    finally:
        db.close()


@bp.post("/api/fonts")
@login_required
def upload_font():
    settings = get_settings()
    font = request.files.get("font")
    if not font:
        return _json({"error": "Font file is required"}, 400)
    path = settings.assets_dir / "fonts" / secure_filename(font.filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    font.save(path)
    return _json({"path": str(path.relative_to(BASE_DIR))}, 201)
