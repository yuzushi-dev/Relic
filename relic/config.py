"""Configuration management for relic runtime governance."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    """Database configuration."""

    path: Path = Field(default_factory=lambda: Path.home() / ".relic" / "relic.db")
    echo_sql: bool = Field(default=False)


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO")
    format_json: bool = Field(default=False)


class RuntimeConfig(BaseModel):
    """Runtime governance configuration."""

    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    schema_version: str = Field(default="0.1.0")


def get_config() -> RuntimeConfig:
    """Get runtime configuration from environment and defaults."""
    return RuntimeConfig(
        db=DatabaseConfig(
            path=Path(os.environ.get("RELIC_DB_PATH", "")) if os.environ.get("RELIC_DB_PATH") else DatabaseConfig().path,
            echo_sql=os.environ.get("RELIC_ECHO_SQL", "").lower() in ("1", "true"),
        ),
        logging=LoggingConfig(
            level=os.environ.get("RELIC_LOG_LEVEL", "INFO"),
            format_json=os.environ.get("RELIC_LOG_JSON", "").lower() in ("1", "true"),
        ),
    )
