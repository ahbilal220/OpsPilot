from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: SecretStr = SecretStr("postgresql+asyncpg://opspilot:local@localhost/opspilot")
    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")
    session_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    cookie_secure: bool = True
    frontend_origin: str = "http://localhost:3000"
    api_origin: str = "http://localhost:8000"
    additional_trusted_origins: str = ""
    registration_enabled: bool = False
    registration_default_role: Literal["viewer", "engineer"] = "viewer"
    investigation_execution_mode: Literal["celery", "inline"] = "celery"
    frontend_static_dir: Path | None = None
    prometheus_url: str = "http://localhost:9090"
    tool_fixture_root: Path = Path("tool-fixtures")
    tool_repository_root: Path = Path("tool-repository")
    tool_max_output_chars: int = Field(default=50000, ge=1000, le=200000)
    investigation_max_iterations: int = Field(default=12, ge=4, le=30)
    investigation_tool_budget: int = Field(default=10, ge=1, le=100)
    investigation_model_budget_usd: Decimal = Field(default=Decimal("0.25"), ge=0, le=100)
    investigation_max_seconds: int = Field(default=60, ge=10, le=600)
    diagnosis_confidence_threshold: Decimal = Field(default=Decimal("0.75"), ge=0, le=1)
    model_provider: str = "fixture"

    @field_validator("database_url", mode="before")
    @classmethod
    def async_postgres_driver(cls, value: object) -> object:
        raw = value.get_secret_value() if isinstance(value, SecretStr) else value
        if isinstance(raw, str) and raw.startswith("postgresql://"):
            return SecretStr(raw.replace("postgresql://", "postgresql+asyncpg://", 1))
        return value

    @property
    def trusted_origins(self) -> frozenset[str]:
        additional = {
            origin.strip().rstrip("/")
            for origin in self.additional_trusted_origins.split(",")
            if origin.strip()
        }
        return frozenset(
            {
                self.frontend_origin.rstrip("/"),
                self.api_origin.rstrip("/"),
                *additional,
            }
        )
