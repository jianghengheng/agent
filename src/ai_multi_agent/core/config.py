from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Multi-Agent Starter"
    app_version: str = "0.1.0"
    app_env: str = "local"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    ark_api_key: str | None = None
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    ark_model: str = Field(
        default="mimo-v2-pro",
        validation_alias=AliasChoices(
            "ARK_MODEL",
            "DOUBAO_MODEL",
            "ark_model",
            "doubao_model",
        ),
    )
    default_max_revisions: int = Field(default=1, ge=0, le=5)
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: [
            "http://127.0.0.1:5173",
            "http://localhost:5173",
        ]
    )

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[3] / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def doubao_model(self) -> str:
        # Backward compatibility for callers still using the old field name.
        return self.ark_model


@lru_cache
def get_settings() -> Settings:
    return Settings()
