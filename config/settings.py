from functools import lru_cache
import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    secret_key: str = Field(default="change-me", alias="SECRET_KEY")
    timezone: str = "Asia/Tashkent"
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/vocabulary_bot"

    telegram_bot_token: str = ""
    telegram_channel_id: str = ""
    telegram_parse_mode: str = "HTML"

    openai_api_key: str = ""
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice_uk: str = "alloy"

    google_service_account_file: str = "credentials.json"
    google_service_account_json: str = ""
    google_drive_root_folder_name: str = "writing-telegram-channel"
    google_drive_root_folder_id: str = ""

    admin_host: str = "0.0.0.0"
    admin_port: int = 5050
    default_admin_username: str = "admin"
    default_admin_password: str = "change-me-now"
    start_scheduler_with_admin: bool = True

    assets_dir: Path = BASE_DIR / "assets"
    template_config_dir: Path = BASE_DIR / "assets" / "templates"
    generated_image_dir: Path = BASE_DIR / "assets" / "generated"
    generated_audio_dir: Path = BASE_DIR / "assets" / "audio"

    @property
    def google_credentials_path(self) -> Path:
        candidate = Path(self.google_service_account_file)
        return candidate if candidate.is_absolute() else BASE_DIR / candidate

    @property
    def bind_port(self) -> int:
        return int(os.getenv("PORT") or self.admin_port)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    for path in (
        settings.assets_dir,
        settings.template_config_dir,
        settings.generated_image_dir,
        settings.generated_audio_dir,
        BASE_DIR / "logs",
    ):
        path.mkdir(parents=True, exist_ok=True)
    return settings
