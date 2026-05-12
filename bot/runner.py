from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from config.settings import get_settings

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("start"))
async def start(message: Message) -> None:
    await message.answer("Multilevel Essays publisher is online. Publishing is managed from the admin panel.")


@router.message(Command("health"))
async def health(message: Message) -> None:
    await message.answer("OK")


async def run_bot() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    bot = Bot(token=settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    logger.info("Starting aiogram polling")
    await dp.start_polling(bot)
