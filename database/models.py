from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from flask_login import UserMixin
from sqlalchemy import Boolean, Date, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.session import Base


class WordStatus(str, Enum):
    NEW = "new"
    QUEUED = "queued"
    POSTED = "posted"
    SKIPPED = "skipped"
    FAILED = "failed"


class PostStatus(str, Enum):
    QUEUED = "queued"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Accent(str, Enum):
    UK = "uk"
    US = "us"


class Word(Base):
    __tablename__ = "words"
    __table_args__ = (UniqueConstraint("source_file_id", "source_row_key", name="uq_word_source_row"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_file_id: Mapped[int | None] = mapped_column(ForeignKey("drive_source_files.id"), index=True)
    source_row_key: Mapped[str | None] = mapped_column(String(160), index=True)
    source_index: Mapped[int | None] = mapped_column(Integer, index=True)
    word: Mapped[str] = mapped_column(String(255), index=True)
    word_type: Mapped[str | None] = mapped_column(String(80), index=True)
    phonetic: Mapped[str | None] = mapped_column(String(255))
    definition: Mapped[str] = mapped_column(Text)
    example: Mapped[str | None] = mapped_column(Text)
    level: Mapped[str | None] = mapped_column(String(64), index=True)
    accent: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[WordStatus] = mapped_column(SqlEnum(WordStatus), default=WordStatus.NEW, index=True)
    source_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    source_file: Mapped["DriveSourceFile | None"] = relationship(back_populates="words")
    posts: Mapped[list["Post"]] = relationship(back_populates="word", cascade="all, delete-orphan")
    audio_files: Mapped[list["AudioFile"]] = relationship(back_populates="word", cascade="all, delete-orphan")


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    image_path: Mapped[str] = mapped_column(String(500))
    config_path: Mapped[str] = mapped_column(String(500))
    image_drive_file_id: Mapped[str | None] = mapped_column(String(160), index=True)
    config_drive_file_id: Mapped[str | None] = mapped_column(String(160), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    posts: Mapped[list["Post"]] = relationship(back_populates="template")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), index=True)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("templates.id"))
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("generation_batches.id"), index=True)
    schedule_id: Mapped[int | None] = mapped_column(ForeignKey("schedules.id"), index=True)
    status: Mapped[PostStatus] = mapped_column(SqlEnum(PostStatus), default=PostStatus.QUEUED, index=True)
    caption: Mapped[str | None] = mapped_column(Text)
    generated_image_path: Mapped[str | None] = mapped_column(String(500))
    image_drive_file_id: Mapped[str | None] = mapped_column(String(160), index=True)
    audio_drive_file_id: Mapped[str | None] = mapped_column(String(160), index=True)
    telegram_message_id: Mapped[str | None] = mapped_column(String(128))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    word: Mapped[Word] = relationship(back_populates="posts")
    template: Mapped[Template | None] = relationship(back_populates="posts")
    batch: Mapped["GenerationBatch | None"] = relationship(back_populates="posts")
    schedule: Mapped["Schedule | None"] = relationship(back_populates="posts")


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    content_type: Mapped[str] = mapped_column(String(48), default="vocabulary", index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("generation_batches.id"), index=True)
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Tashkent")
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    dispatch_mode: Mapped[str] = mapped_column(String(32), default="even")
    window_start: Mapped[str | None] = mapped_column(String(16))
    window_end: Mapped[str | None] = mapped_column(String(16))
    manual_times: Mapped[list[str]] = mapped_column(JSONB, default=list)
    scheduled_post_count: Mapped[int] = mapped_column(Integer, default=0)
    days: Mapped[list[str]] = mapped_column(JSONB, default=list)
    times: Mapped[list[str]] = mapped_column(JSONB, default=list)
    posts_per_day: Mapped[int] = mapped_column(Integer, default=1)
    random_interval_minutes: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    batch: Mapped["GenerationBatch | None"] = relationship(back_populates="schedules")
    posts: Mapped[list[Post]] = relationship(back_populates="schedule")


class AudioFile(Base):
    __tablename__ = "audio_files"
    __table_args__ = (UniqueConstraint("word_id", "accent", name="uq_audio_word_accent"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), index=True)
    accent: Mapped[Accent] = mapped_column(SqlEnum(Accent), index=True)
    file_path: Mapped[str] = mapped_column(String(500))
    voice: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    word: Mapped[Word] = relationship(back_populates="audio_files")


class VocabularyCollection(Base):
    __tablename__ = "vocabulary_collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    drive_folder_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    source_folder_id: Mapped[str] = mapped_column(String(160), unique=True)
    generated_folder_id: Mapped[str] = mapped_column(String(160), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source_files: Mapped[list["DriveSourceFile"]] = relationship(back_populates="collection", cascade="all, delete-orphan")
    batches: Mapped[list["GenerationBatch"]] = relationship(back_populates="collection", cascade="all, delete-orphan")


class DriveSourceFile(Base):
    __tablename__ = "drive_source_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("vocabulary_collections.id"), index=True)
    drive_file_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    drive_parent_id: Mapped[str | None] = mapped_column(String(160), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    mime_type: Mapped[str | None] = mapped_column(String(160))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    collection: Mapped[VocabularyCollection] = relationship(back_populates="source_files")
    words: Mapped[list[Word]] = relationship(back_populates="source_file")
    batches: Mapped[list["GenerationBatch"]] = relationship(back_populates="source_file")


class GenerationBatch(Base):
    __tablename__ = "generation_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("vocabulary_collections.id"), index=True)
    source_file_id: Mapped[int] = mapped_column(ForeignKey("drive_source_files.id"), index=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("templates.id"), index=True)
    name: Mapped[str] = mapped_column(String(180), index=True)
    status: Mapped[str] = mapped_column(String(48), default="generating", index=True)
    caption_text: Mapped[str | None] = mapped_column(Text)
    settings_payload: Mapped[dict | None] = mapped_column(JSONB)
    generated_folder_id: Mapped[str | None] = mapped_column(String(160))
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    generated_items: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    collection: Mapped[VocabularyCollection] = relationship(back_populates="batches")
    source_file: Mapped[DriveSourceFile] = relationship(back_populates="batches")
    template: Mapped[Template] = relationship()
    posts: Mapped[list[Post]] = relationship(back_populates="batch", cascade="all, delete-orphan")
    schedules: Mapped[list[Schedule]] = relationship(back_populates="batch")


class AdminUser(UserMixin, Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active_user: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def is_active(self) -> bool:  # Flask-Login contract
        return self.is_active_user


class PostingLog(Base):
    __tablename__ = "posting_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int | None] = mapped_column(ForeignKey("posts.id"), index=True)
    level: Mapped[str] = mapped_column(String(40), default="info")
    event: Mapped[str] = mapped_column(String(120), index=True)
    message: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
