from __future__ import annotations

from pathlib import Path

from config.settings import BASE_DIR
from core.google_drive import GoogleDriveStorage
from database.models import Template


def ensure_template_files(template: Template) -> tuple[Path, Path]:
    image_path = BASE_DIR / template.image_path
    config_path = BASE_DIR / template.config_path
    if image_path.exists() and config_path.exists():
        return image_path, config_path

    drive = GoogleDriveStorage()
    image_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not image_path.exists() and template.image_drive_file_id:
        drive.download_to_path(template.image_drive_file_id, image_path)
    if not config_path.exists() and template.config_drive_file_id:
        drive.download_to_path(template.config_drive_file_id, config_path)
    return image_path, config_path
