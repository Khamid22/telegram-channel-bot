from __future__ import annotations

import csv
import io
import re
import tempfile
from datetime import datetime
from hashlib import sha1
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

from core.google_drive import CSV_MIME_TYPES, GoogleDriveStorage
from core.image_renderer import VocabularyImageRenderer
from core.publishing import build_caption
from core.template_storage import ensure_template_files
from core.tts import OpenAITTSService
from database.models import Accent, DriveSourceFile, GenerationBatch, Template, VocabularyCollection
from database.repositories import (
    DriveSourceFileRepository,
    GenerationBatchRepository,
    LogRepository,
    PostRepository,
    VocabularyCollectionRepository,
    WordRepository,
)

HEADER_ALIASES = {
    "name": "word",
    "word": "word",
    "term": "word",
    "vocabulary": "word",
    "word type": "word_type",
    "word-type": "word_type",
    "word_type": "word_type",
    "type": "word_type",
    "part of speech": "word_type",
    "part_of_speech": "word_type",
    "definition": "definition",
    "meaning": "definition",
    "example": "example",
    "example sentence": "example",
    "phonetic": "phonetic",
    "ipa": "phonetic",
    "level": "level",
    "accent": "accent",
}


class GenerationCancelled(RuntimeError):
    pass


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value.lower()).strip("-") or "batch"


def _normalize_header(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").split())


def _source_row_key(file_id: str, row_index: int, payload: dict[str, Any]) -> str:
    base = f"{file_id}|{row_index}|{payload.get('word', '')}|{payload.get('definition', '')}"
    return sha1(base.encode("utf-8")).hexdigest()[:20]


def parse_vocabulary_csv(data: bytes, *, file_id: str = "local") -> list[dict[str, Any]]:
    text = data.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV must include a header row.")

    rows: list[dict[str, Any]] = []
    for row_index, raw in enumerate(reader, start=1):
        normalized: dict[str, Any] = {"extra": {}}
        for header, value in raw.items():
            header_text = str(header or "").strip()
            normalized_header = _normalize_header(header_text)
            canonical = HEADER_ALIASES.get(normalized_header)
            cleaned = str(value or "").strip()
            if canonical:
                normalized[canonical] = cleaned
            else:
                normalized["extra"][header_text or f"column_{len(normalized['extra']) + 1}"] = cleaned

        if not normalized.get("word") or not normalized.get("definition"):
            continue
        normalized["source_row_key"] = _source_row_key(file_id, row_index, normalized)
        normalized["source_index"] = row_index
        rows.append(normalized)

    if not rows:
        raise ValueError("CSV must contain at least one row with Name and Definition values.")
    return rows


class VocabularyGeneratorService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.drive = GoogleDriveStorage()
        self.collections = VocabularyCollectionRepository(db)
        self.sources = DriveSourceFileRepository(db)
        self.batches = GenerationBatchRepository(db)
        self.words = WordRepository(db)
        self.posts = PostRepository(db)
        self.logs = LogRepository(db)

    def refresh_drive_catalog(self) -> dict[str, list[dict[str, Any]]]:
        structure = self.drive.ensure_root_structure()
        collection_payloads = []
        source_payloads = []

        for item in structure["collections"]:
            collection = self.collections.upsert(**item)
            collection_payloads.append(collection)
            for drive_file in self.drive.list_files(collection.source_folder_id, CSV_MIME_TYPES):
                source = self.sources.upsert(
                    collection=collection,
                    drive_file_id=drive_file.id,
                    drive_parent_id=collection.source_folder_id,
                    name=drive_file.name,
                    mime_type=drive_file.mime_type,
                )
                source_payloads.append(source)

        self.logs.add("drive_refresh", "Refreshed Google Drive vocabulary catalog")
        self.db.commit()
        return {
            "collections": collection_payloads,
            "sources": source_payloads,
        }

    def upload_source(self, collection: VocabularyCollection, filename: str, data: bytes) -> tuple[DriveSourceFile, list[dict[str, Any]]]:
        rows = parse_vocabulary_csv(data)
        item = self.drive.upload_bytes(data, name=filename, parent_id=collection.source_folder_id, mime_type="text/csv")
        rows = parse_vocabulary_csv(data, file_id=item.id)
        source = self.sources.upsert(
            collection=collection,
            drive_file_id=item.id,
            drive_parent_id=collection.source_folder_id,
            name=item.name,
            mime_type=item.mime_type,
            row_count=len(rows),
        )
        self.logs.add("drive_source_upload", f"Uploaded {item.name} to Google Drive")
        self.db.commit()
        return source, rows

    def rows_for_source(self, source: DriveSourceFile) -> list[dict[str, Any]]:
        rows = parse_vocabulary_csv(self.drive.download_bytes(source.drive_file_id), file_id=source.drive_file_id)
        source.row_count = len(rows)
        self.db.commit()
        return rows

    def generate_batch(
        self,
        *,
        source: DriveSourceFile,
        template: Template,
        name: str,
        caption_text: str,
        settings_payload: dict[str, Any] | None = None,
        progress_callback: Callable[[GenerationBatch], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> GenerationBatch:
        rows = self.rows_for_source(source)
        batch = GenerationBatch(
            collection=source.collection,
            source_file=source,
            template=template,
            name=name.strip() or f"{source.name} - {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            caption_text=caption_text.strip() or None,
            settings_payload=settings_payload or {},
            total_items=len(rows),
            generated_items=0,
            status="generating",
        )
        self.db.add(batch)
        self.db.flush()
        self.db.commit()
        if progress_callback:
            progress_callback(batch)

        if should_cancel and should_cancel():
            batch.status = "cancelled"
            self.db.commit()
            if progress_callback:
                progress_callback(batch)
            raise GenerationCancelled("Generation cancelled.")

        generated_folder_id = self.drive.ensure_folder(f"batch-{batch.id}-{_slug(batch.name)}", source.collection.generated_folder_id)
        batch.generated_folder_id = generated_folder_id
        self.db.commit()

        ensure_template_files(template)
        renderer = VocabularyImageRenderer(template.config_path)
        tts = OpenAITTSService()

        with tempfile.TemporaryDirectory(prefix="writing-telegram-channel-") as temp_dir:
            output_dir = Path(temp_dir)
            for source_index, row in enumerate(rows, start=1):
                if should_cancel and should_cancel():
                    batch.status = "cancelled"
                    self.db.commit()
                    if progress_callback:
                        progress_callback(batch)
                    raise GenerationCancelled("Generation cancelled.")

                word = self.words.upsert_from_source(source, row, source_index)
                self.db.flush()

                image_path = renderer.render(word, template.config_path, output_dir=output_dir)
                audio_path = tts.generate(word, Accent.UK, output_dir=output_dir)
                image_drive = self.drive.upload_file(
                    image_path,
                    name=image_path.name,
                    parent_id=generated_folder_id,
                    mime_type="image/png",
                )
                audio_drive = self.drive.upload_file(
                    audio_path,
                    name=audio_path.name,
                    parent_id=generated_folder_id,
                    mime_type="audio/mpeg",
                )

                self.posts.create_for_word(
                    word,
                    template,
                    batch=batch,
                    caption=build_caption(word, caption_text),
                    image_drive_file_id=image_drive.id,
                    audio_drive_file_id=audio_drive.id,
                )
                batch.generated_items += 1
                self.db.commit()
                if progress_callback:
                    progress_callback(batch)

        batch.status = "ready"
        self.logs.add("batch_generated", f"Generated {batch.generated_items} vocabulary posts", payload={"batch_id": batch.id})
        self.db.commit()
        if progress_callback:
            progress_callback(batch)
        return batch
