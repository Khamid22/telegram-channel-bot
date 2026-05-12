from __future__ import annotations

import logging
from pathlib import Path

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import get_settings
from database.models import Accent, Word

logger = logging.getLogger(__name__)


class OpenAITTSService:
    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        self.client = OpenAI(api_key=self.settings.openai_api_key)

    @retry(wait=wait_exponential(multiplier=1, min=2, max=20), stop=stop_after_attempt(3), reraise=True)
    def generate(self, word: Word, accent: Accent) -> Path:
        output_dir = self.settings.generated_audio_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        voice = self.settings.openai_tts_voice_uk
        instructions = "Pronounce this word naturally in British English. Speak only the word."
        output_path = output_dir / f"{word.id}-pronunciation-{word.word.lower().replace(' ', '-')}.mp3"

        logger.info("Generating pronunciation for %s", word.word)
        try:
            # The `instructions` parameter was added in a newer SDK version; fall back without it.
            with self.client.audio.speech.with_streaming_response.create(
                model=self.settings.openai_tts_model,
                voice=voice,
                input=word.word,
                instructions=instructions,
                response_format="mp3",
            ) as response:
                response.stream_to_file(output_path)
        except TypeError:
            with self.client.audio.speech.with_streaming_response.create(
                model=self.settings.openai_tts_model,
                voice=voice,
                input=word.word,
                response_format="mp3",
            ) as response:
                response.stream_to_file(output_path)

        return output_path
