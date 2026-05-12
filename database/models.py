from __future__ import annotations

from datetime import datetime
from enum import Enum

from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Integer, String, Text, UniqueConstraint, func
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sheet_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
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

    posts: Mapped[list["Post"]] = relationship(back_populates="word", cascade="all, delete-orphan")
    audio_files: Mapped[list["AudioFile"]] = relationship(back_populates="word", cascade="all, delete-orphan")


class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    image_path: Mapped[str] = mapped_column(String(500))
    config_path: Mapped[str] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    posts: Mapped[list["Post"]] = relationship(back_populates="template")


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id"), index=True)
    template_id: Mapped[int | None] = mapped_column(ForeignKey("templates.id"))
    status: Mapped[PostStatus] = mapped_column(SqlEnum(PostStatus), default=PostStatus.QUEUED, index=True)
    caption: Mapped[str | None] = mapped_column(Text)
    generated_image_path: Mapped[str | None] = mapped_column(String(500))
    telegram_message_id: Mapped[str | None] = mapped_column(String(128))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    word: Mapped[Word] = relationship(back_populates="posts")
    template: Mapped[Template | None] = relationship(back_populates="posts")


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Tashkent")
    days: Mapped[list[str]] = mapped_column(JSONB, default=list)
    times: Mapped[list[str]] = mapped_column(JSONB, default=list)
    posts_per_day: Mapped[int] = mapped_column(Integer, default=1)
    random_interval_minutes: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


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
