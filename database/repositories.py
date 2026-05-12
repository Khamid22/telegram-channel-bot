from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from database.models import Accent, AdminUser, AudioFile, Post, PostingLog, PostStatus, Schedule, Template, Word, WordStatus


class WordRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert_from_sheet(self, row: dict[str, Any]) -> Word:
        word = self.db.scalar(select(Word).where(Word.sheet_id == str(row["id"])))
        if not word:
            word = Word(sheet_id=str(row["id"]), word=row["word"], definition=row["definition"])
            self.db.add(word)

        word.word = row["word"].strip()
        word.word_type = row.get("word_type")
        word.phonetic = row.get("phonetic")
        word.definition = row["definition"].strip()
        word.example = row.get("example")
        word.level = row.get("level")
        word.accent = row.get("accent")
        word.status = WordStatus(row.get("status", "new").lower()) if row.get("status", "").lower() in WordStatus._value2member_map_ else WordStatus.NEW
        word.source_payload = row
        return word

    def next_for_queue(self) -> Word | None:
        return self.db.scalar(
            select(Word)
            .where(Word.status.in_([WordStatus.NEW, WordStatus.QUEUED, WordStatus.FAILED]))
            .order_by(Word.created_at.asc())
            .limit(1)
        )

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

    def create_for_word(self, word: Word, template: Template | None, scheduled_at: datetime | None = None) -> Post:
        post = Post(word=word, template=template, scheduled_at=scheduled_at, status=PostStatus.QUEUED)
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
