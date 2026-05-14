"""Path management for relic runtime governance."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path


def get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent


def get_relic_home() -> Path:
    """Get relic home directory for user data."""
    env_val = os.environ.get("RELIC_HOME", "").strip()
    if env_val:
        return Path(env_val)
    return Path.home() / ".relic"


def get_db_path() -> Path:
    """Get database path."""
    return get_relic_home() / "relic.db"


def get_fixtures_dir() -> Path:
    """Get fixtures directory."""
    return get_project_root() / "fixtures"


def get_migrations_dir() -> Path:
    """Get migrations directory."""
    return get_project_root() / "relic" / "db" / "migrations"


def get_schema_version() -> str:
    """Read current schema version from migrations."""
    migrations = get_migrations_dir()
    versions = []
    for f in migrations.glob("*.sql"):
        if m := f.stem.split("_")[0]:
            versions.append(m)
    if versions:
        versions.sort()
        return versions[-1]
    return "0"


def iter_migrations() -> Iterator[Path]:
    """Iterate over migration files in order."""
    migrations = get_migrations_dir()
    yield from sorted(migrations.glob("[0-9]*.sql"))
