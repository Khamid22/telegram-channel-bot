from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from database.models import Post, PostStatus, Word
from database.repositories import LogRepository, PostRepository
from core.google_drive import GoogleDriveStorage
from core.telegram import TelegramPublisher

logger = logging.getLogger(__name__)


def build_caption(word: Word, custom_caption: str | None = None) -> str:
    tags = ["#english", "#ielts"]
    if word.level:
        tags.append(f"#{word.level.upper().replace(' ', '')}")
    if word.word_type:
        tags.append(f"#{word.word_type.lower().replace(' ', '')}")
    parts = [part for part in ((custom_caption or "").strip(), " ".join(tags)) if part]
    return "\n\n".join(parts)


class PublishingService:
    def __init__(self, db: Session):
        self.db = db
        self.posts = PostRepository(db)
        self.logs = LogRepository(db)
        self.drive = GoogleDriveStorage()

    def ensure_post(self) -> Post:
        post = self.posts.next_queued()
        if post:
            return post
        raise RuntimeError("No generated posts are queued")

    async def publish_next(self) -> Post:
        post = self.ensure_post()
        return await self.publish(post)

    async def publish(self, post: Post) -> Post:
        post.status = PostStatus.PUBLISHING
        self.db.commit()

        try:
            if not post.image_drive_file_id or not post.audio_drive_file_id:
                raise RuntimeError("Generated Drive assets are missing for this post")
            telegram = TelegramPublisher()
            with tempfile.TemporaryDirectory(prefix="writing-telegram-post-") as temp_dir:
                temp_path = Path(temp_dir)
                image_path = self.drive.download_to_path(post.image_drive_file_id, temp_path / f"post-{post.id}.png")
                audio_path = self.drive.download_to_path(post.audio_drive_file_id, temp_path / f"post-{post.id}.mp3")
                try:
                    message = await telegram.send_vocabulary_post(image_path, post.caption or build_caption(post.word))
                    await telegram.send_audio(audio_path, post.word.word, "multilevel essays")
                finally:
                    await telegram.close()

            self.posts.mark_published(post, message.message_id)
            self.logs.add("publish_success", f"Published {post.word.word}", post_id=post.id)
            self.db.commit()
            return post
        except Exception as exc:
            logger.exception("Publishing failed for post %s", post.id)
            self.posts.mark_failed(post, str(exc))
            self.logs.add("publish_failed", str(exc), post_id=post.id, level="error")
            self.db.commit()
            raise
