from __future__ import annotations

from pathlib import Path
from typing import Any

from database.models import (
    DriveSourceFile,
    GenerationBatch,
    Post,
    Schedule,
    Template,
    VocabularyCollection,
    Word,
)


def word_payload(word: Word) -> dict[str, Any]:
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


def post_payload(post: Post) -> dict[str, Any]:
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
        "word": word_payload(post.word),
        "audio": (
            [{"id": f"post-{post.id}", "url": f"/api/posts/{post.id}/audio", "voice": "multilevel essays"}]
            if post.audio_drive_file_id
            else []
        ),
        "batch": batch_payload(post.batch) if post.batch else None,
    }


def schedule_payload(schedule: Schedule) -> dict[str, Any]:
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


def template_payload(template: Template) -> dict[str, Any]:
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


def collection_payload(collection: VocabularyCollection) -> dict[str, Any]:
    return {
        "id": collection.id,
        "name": collection.name,
        "slug": collection.slug,
        "drive_folder_id": collection.drive_folder_id,
        "source_folder_id": collection.source_folder_id,
        "generated_folder_id": collection.generated_folder_id,
    }


def source_payload(source: DriveSourceFile) -> dict[str, Any]:
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


def batch_payload(batch: GenerationBatch) -> dict[str, Any]:
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
