"""Database loader utilities for relic."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from relic.paths import get_fixtures_dir, get_migrations_dir


def load_migration(migration_path: Path) -> str:
    """Load migration SQL from file."""
    return migration_path.read_text(encoding="utf-8")


def load_fixture_sql(fixture_name: str) -> str:
    """Load fixture SQL from fixtures directory."""
    fixture_path = get_fixtures_dir() / fixture_name / "initial_db_state.sql"
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_name}")
    return fixture_path.read_text(encoding="utf-8")


def iter_migrations() -> Iterator[Path]:
    """Iterate over all migration files in order."""
    migrations = get_migrations_dir()
    yield from sorted(migrations.glob("[0-9]*.sql"))


def iter_fixtures() -> Iterator[str]:
    """Iterate over available fixture names."""
    fixtures = get_fixtures_dir()
    for path in fixtures.iterdir():
        if path.is_dir() and (path / "initial_db_state.sql").exists():
            yield path.name
