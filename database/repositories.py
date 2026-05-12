from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from database.models import (
    Accent,
    AdminUser,
    AudioFile,
    DriveSourceFile,
    GenerationBatch,
    Post,
    PostingLog,
    PostStatus,
    Schedule,
    Template,
    VocabularyCollection,
    Word,
    WordStatus,
)


class WordRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert_from_source(self, source_file: DriveSourceFile, row: dict[str, Any], source_index: int) -> Word:
        source_row_key = str(row["source_row_key"])
        word = self.db.scalar(
            select(Word).where(
                Word.source_file_id == source_file.id,
                Word.source_row_key == source_row_key,
            )
        )
        if not word:
            word = Word(
                source_file=source_file,
                source_row_key=source_row_key,
                source_index=source_index,
                word=row["word"],
                definition=row["definition"],
            )
            self.db.add(word)

        word.word = row["word"].strip()
        word.word_type = row.get("word_type")
        word.phonetic = row.get("phonetic")
        word.definition = row["definition"].strip()
        word.example = row.get("example")
        word.level = row.get("level")
        word.accent = row.get("accent")
        word.status = WordStatus.NEW if word.status not in (WordStatus.QUEUED, WordStatus.POSTED) else word.status
        word.source_index = source_index
        word.source_payload = row
        return word

    def list_words(self, limit: int = 100, status: str | None = None) -> list[Word]:
        stmt = select(Word).order_by(desc(Word.created_at)).limit(limit)
        if status:
            stmt = stmt.where(Word.status == WordStatus(status))
        return list(self.db.scalars(stmt))


class TemplateRepository:
    def __init__(self, db: Session):
        self.db = db

    def active(self) -> Template | None:
        return self.db.scalar(select(Template).where(Template.is_active.is_(True)).limit(1))

    def set_active(self, template_id: int) -> Template:
        templates = list(self.db.scalars(select(Template)))
        selected = None
        for template in templates:
            template.is_active = template.id == template_id
            if template.id == template_id:
                selected = template
        if not selected:
            raise ValueError("Template not found")
        return selected

    def list(self) -> list[Template]:
        return list(self.db.scalars(select(Template).order_by(desc(Template.created_at))))


class PostRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_for_word(
        self,
        word: Word,
        template: Template | None,
        *,
        batch: GenerationBatch | None = None,
        caption: str | None = None,
        image_drive_file_id: str | None = None,
        audio_drive_file_id: str | None = None,
        scheduled_at: datetime | None = None,
    ) -> Post:
        post = Post(
            word=word,
            template=template,
            batch=batch,
            caption=caption,
            image_drive_file_id=image_drive_file_id,
            audio_drive_file_id=audio_drive_file_id,
            scheduled_at=scheduled_at,
            status=PostStatus.QUEUED,
        )
        word.status = WordStatus.QUEUED
        self.db.add(post)
        return post

    def queued(self, limit: int = 50) -> list[Post]:
        return list(
            self.db.scalars(
                select(Post)
                .where(Post.status == PostStatus.QUEUED)
                .order_by(Post.scheduled_at.asc().nullsfirst(), Post.created_at.asc())
                .limit(limit)
            )
        )

    def next_queued(self) -> Post | None:
        return self.db.scalar(
            select(Post)
            .where(Post.status == PostStatus.QUEUED)
            .order_by(Post.scheduled_at.asc().nullsfirst(), Post.created_at.asc())
            .limit(1)
        )

    def due(self, now: datetime, limit: int = 20) -> list[Post]:
        return list(
            self.db.scalars(
                select(Post)
                .join(Schedule, Post.schedule_id == Schedule.id)
                .where(
                    Post.status == PostStatus.QUEUED,
                    Post.scheduled_at.is_not(None),
                    Post.scheduled_at <= now,
                    Schedule.is_active.is_(True),
                    Schedule.is_paused.is_(False),
                )
                .order_by(Post.scheduled_at.asc())
                .limit(limit)
            )
        )

    def unscheduled_for_batch(self, batch_id: int, limit: int | None = None) -> list[Post]:
        stmt = (
            select(Post)
            .join(Word, Post.word_id == Word.id)
            .where(
                Post.batch_id == batch_id,
                Post.status == PostStatus.QUEUED,
                Post.scheduled_at.is_(None),
            )
            .order_by(Word.source_index.asc().nulls_last(), Post.created_at.asc())
        )
        if limit:
            stmt = stmt.limit(limit)
        return list(self.db.scalars(stmt))

    def mark_published(self, post: Post, message_id: str | int | None) -> None:
        post.status = PostStatus.PUBLISHED
        post.telegram_message_id = str(message_id) if message_id else None
        post.published_at = datetime.now(timezone.utc)
        post.error_message = None
        post.word.status = WordStatus.POSTED

    def mark_failed(self, post: Post, message: str) -> None:
        post.status = PostStatus.FAILED
        post.error_message = message
        post.word.status = WordStatus.FAILED

    def failed(self, limit: int = 100) -> list[Post]:
        return list(self.db.scalars(select(Post).where(Post.status == PostStatus.FAILED).order_by(desc(Post.updated_at)).limit(limit)))


class AudioRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, word_id: int, accent: Accent) -> AudioFile | None:
        return self.db.scalar(select(AudioFile).where(AudioFile.word_id == word_id, AudioFile.accent == accent).limit(1))

    def save(self, word_id: int, accent: Accent, path: str, voice: str) -> AudioFile:
        audio = self.get(word_id, accent)
        if not audio:
            audio = AudioFile(word_id=word_id, accent=accent, file_path=path, voice=voice)
            self.db.add(audio)
        else:
            audio.file_path = path
            audio.voice = voice
        return audio


class ScheduleRepository:
    def __init__(self, db: Session):
        self.db = db

    def active(self) -> list[Schedule]:
        return list(self.db.scalars(select(Schedule).where(Schedule.is_active.is_(True)).order_by(Schedule.name.asc())))

    def list(self) -> list[Schedule]:
        return list(self.db.scalars(select(Schedule).order_by(desc(Schedule.created_at))))


class VocabularyCollectionRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self) -> list[VocabularyCollection]:
        return list(self.db.scalars(select(VocabularyCollection).order_by(VocabularyCollection.name.asc())))

    def get(self, collection_id: int) -> VocabularyCollection | None:
        return self.db.get(VocabularyCollection, collection_id)

    def upsert(
        self,
        *,
        name: str,
        slug: str,
        drive_folder_id: str,
        source_folder_id: str,
        generated_folder_id: str,
    ) -> VocabularyCollection:
        collection = self.db.scalar(select(VocabularyCollection).where(VocabularyCollection.drive_folder_id == drive_folder_id))
        if not collection:
            collection = VocabularyCollection(
                name=name,
                slug=slug,
                drive_folder_id=drive_folder_id,
                source_folder_id=source_folder_id,
                generated_folder_id=generated_folder_id,
            )
            self.db.add(collection)
        else:
            collection.name = name
            collection.slug = slug
            collection.source_folder_id = source_folder_id
            collection.generated_folder_id = generated_folder_id
        return collection


class DriveSourceFileRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, source_file_id: int) -> DriveSourceFile | None:
        return self.db.get(DriveSourceFile, source_file_id)

    def by_drive_id(self, drive_file_id: str) -> DriveSourceFile | None:
        return self.db.scalar(select(DriveSourceFile).where(DriveSourceFile.drive_file_id == drive_file_id))

    def list(self) -> list[DriveSourceFile]:
        return list(self.db.scalars(select(DriveSourceFile).order_by(desc(DriveSourceFile.updated_at))))

    def upsert(
        self,
        *,
        collection: VocabularyCollection,
        drive_file_id: str,
        drive_parent_id: str | None,
        name: str,
        mime_type: str | None,
        row_count: int | None = None,
    ) -> DriveSourceFile:
        source = self.by_drive_id(drive_file_id)
        if not source:
            source = DriveSourceFile(
                collection=collection,
                drive_file_id=drive_file_id,
                drive_parent_id=drive_parent_id,
                name=name,
                mime_type=mime_type,
                row_count=row_count or 0,
            )
            self.db.add(source)
        else:
            source.collection = collection
            source.drive_parent_id = drive_parent_id
            source.name = name
            source.mime_type = mime_type
            if row_count is not None:
                source.row_count = row_count
        return source


class GenerationBatchRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, batch_id: int) -> GenerationBatch | None:
        return self.db.get(GenerationBatch, batch_id)

    def list(self) -> list[GenerationBatch]:
        return list(self.db.scalars(select(GenerationBatch).order_by(desc(GenerationBatch.created_at))))


class AdminRepository:
    def __init__(self, db: Session):
        self.db = db

    def by_username(self, username: str) -> AdminUser | None:
        return self.db.scalar(select(AdminUser).where(AdminUser.username == username).limit(1))

    def by_id(self, user_id: int) -> AdminUser | None:
        return self.db.get(AdminUser, user_id)


class LogRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, event: str, message: str | None = None, *, post_id: int | None = None, level: str = "info", payload: dict | None = None) -> PostingLog:
        log = PostingLog(post_id=post_id, level=level, event=event, message=message, payload=payload)
        self.db.add(log)
        return log


def analytics_summary(db: Session) -> dict[str, Any]:
    counts = {
        "words": db.scalar(select(func.count(Word.id))) or 0,
        "queued": db.scalar(select(func.count(Post.id)).where(Post.status == PostStatus.QUEUED)) or 0,
        "published": db.scalar(select(func.count(Post.id)).where(Post.status == PostStatus.PUBLISHED)) or 0,
        "failed": db.scalar(select(func.count(Post.id)).where(Post.status == PostStatus.FAILED)) or 0,
        "templates": db.scalar(select(func.count(Template.id))) or 0,
    }
    recent_logs = list(db.scalars(select(PostingLog).order_by(desc(PostingLog.created_at)).limit(10)))
    counts["recent_logs"] = [
        {
            "id": log.id,
            "level": log.level,
            "event": log.event,
            "message": log.message,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in recent_logs
    ]
    return counts
