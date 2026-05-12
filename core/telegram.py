from __future__ import annotations

import logging
from pathlib import Path

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile, Message
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import get_settings

logger = logging.getLogger(__name__)


class TelegramPublisher:
    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.telegram_bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
        if not self.settings.telegram_channel_id:
            raise RuntimeError("TELEGRAM_CHANNEL_ID is not configured")
        parse_mode = ParseMode.HTML if self.settings.telegram_parse_mode.upper() == "HTML" else None
        self.bot = Bot(token=self.settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=parse_mode))

    @retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(3), reraise=True)
    async def send_vocabulary_post(self, image_path: Path, caption: str) -> Message:
        logger.info("Sending Telegram image post: %s", image_path)
        return await self.bot.send_photo(
            chat_id=self.settings.telegram_channel_id,
            photo=FSInputFile(image_path),
            caption=caption,
        )

    @retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(3), reraise=True)
    async def send_audio(self, audio_path: Path, title: str, performer: str) -> Message:
        logger.info("Sending Telegram audio: %s", audio_path)
        return await self.bot.send_audio(
            chat_id=self.settings.telegram_channel_id,
            audio=FSInputFile(audio_path),
            title=title,
            performer=performer,
        )

    async def close(self) -> None:
        await self.bot.session.close()
