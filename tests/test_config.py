"""Tests for relic configuration."""

from __future__ import annotations

import os
from pathlib import Path

from relic.config import DatabaseConfig, LoggingConfig, RuntimeConfig, get_config


def test_database_config_defaults():
    """Database config has sensible defaults."""
    config = DatabaseConfig()
    assert isinstance(config.path, Path)
    assert "relic" in str(config.path)
    assert config.echo_sql is False


def test_logging_config_defaults():
    """Logging config has sensible defaults."""
    config = LoggingConfig()
    assert config.level == "INFO"
    assert config.format_json is False


def test_runtime_config_has_nested_configs():
    """Runtime config contains nested config objects."""
    config = RuntimeConfig()
    assert isinstance(config.db, DatabaseConfig)
    assert isinstance(config.logging, LoggingConfig)


def test_runtime_config_schema_version():
    """Runtime config has schema version."""
    config = RuntimeConfig()
    assert config.schema_version == "0.1.0"


def test_get_config_from_env():
    """get_config respects environment variables."""
    os.environ["RELIC_LOG_LEVEL"] = "DEBUG"
    os.environ["RELIC_LOG_JSON"] = "true"
    try:
        config = get_config()
        assert config.logging.level == "DEBUG"
        assert config.logging.format_json is True
    finally:
        os.environ.pop("RELIC_LOG_LEVEL", None)
        os.environ.pop("RELIC_LOG_JSON", None)
