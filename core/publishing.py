from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.orm import Session

from database.models import Accent, Post, PostStatus, Word
from database.repositories import AudioRepository, LogRepository, PostRepository, TemplateRepository, WordRepository
from core.image_renderer import VocabularyImageRenderer
from core.telegram import TelegramPublisher
from core.tts import OpenAITTSService

logger = logging.getLogger(__name__)


def build_caption(word: Word) -> str:
    tags = ["#english", "#ielts"]
    if word.level:
        tags.append(f"#{word.level.upper().replace(' ', '')}")
    if word.word_type:
        tags.append(f"#{word.word_type.lower().replace(' ', '')}")
    return " ".join(tags)


class PublishingService:
    def __init__(self, db: Session):
        self.db = db
        self.posts = PostRepository(db)
        self.words = WordRepository(db)
        self.templates = TemplateRepository(db)
        self.audio = AudioRepository(db)
        self.logs = LogRepository(db)

    def ensure_post(self) -> Post:
        post = self.posts.next_queued()
        if post:
            return post

        word = self.words.next_for_queue()
        if not word:
            raise RuntimeError("No words available to publish")
        post = self.posts.create_for_word(word, self.templates.active())
        self.db.commit()
        return post

    async def publish_next(self) -> Post:
        post = self.ensure_post()
        return await self.publish(post)

    async def publish(self, post: Post) -> Post:
        post.status = PostStatus.PUBLISHING
        self.db.commit()

        try:
            template = post.template or self.templates.active()
            renderer = VocabularyImageRenderer(template.config_path if template else None)
            image_path = renderer.render(post.word, template.config_path if template else None)
            caption = build_caption(post.word)

            tts = OpenAITTSService()
            telegram = TelegramPublisher()
            try:
                audio_path = tts.generate(post.word, Accent.UK)
                self.audio.save(post.word.id, Accent.UK, str(audio_path), "multilevel essays")

                message = await telegram.send_vocabulary_post(image_path, caption)
                await telegram.send_audio(Path(audio_path), post.word.word, "multilevel essays")
            finally:
                await telegram.close()

            post.caption = caption
            post.generated_image_path = str(image_path)
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
