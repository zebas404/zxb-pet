from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

Difficulty = Literal["casual", "normal", "hardcore"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    vault_path: Path = Path("/vault")
    data_dir: Path = Path("/data")
    tz: str = "America/Bogota"

    anthropic_api_key: str | None = None
    claude_model: str = "claude-haiku-4-5"
    briefing_max_refresh_per_day: int = 5

    pet_name: str = "Zebot"
    pet_difficulty: Difficulty = "normal"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "zebot.sqlite3"

    def today(self) -> date:
        return datetime.now(ZoneInfo(self.tz)).date()


@lru_cache
def get_settings() -> Settings:
    return Settings()
