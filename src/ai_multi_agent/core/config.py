from functools import lru_cache
from pathlib import Path

from typing import Any

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_env_file_path = Path(__file__).resolve().parents[3] / ".env"


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

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=str(_env_file_path) if _env_file_path.exists() else None,
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
