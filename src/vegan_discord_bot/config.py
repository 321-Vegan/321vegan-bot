from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=True,
        extra="ignore",
    )

    DISCORD_BOT_TOKEN: SecretStr
    DISCORD_APPLICATION_ID: int
    DISCORD_GUILD_ID: int | None = None
    DISCORD_REQUIRED_ROLE_ID: int = 1350810248256159805
    DISCORD_ALLOWED_CHANNEL_ID: int = 1350813080476581918
    DISCORD_SYNC_COMMANDS: bool = False

    VEGAN_API_BASE_URL: str = Field(min_length=1)
    VEGAN_API_EMAIL: str = Field(min_length=1)
    VEGAN_API_PASSWORD: SecretStr


@lru_cache
def get_settings() -> Settings:
    return Settings()
