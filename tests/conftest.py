"""Root pytest configuration, shared fixtures for all test modules."""

from __future__ import annotations

import sys
import sqlite3
from collections.abc import Generator
from pathlib import Path

# Ensure repo-local packages, including the hermes_plugin wrapper, resolve
# before any test imports.
_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest

from relic.db import get_connection, init_db


@pytest.fixture
def temp_db(tmp_path: Path) -> Generator[Path, None, None]:
    """Provide an initialized temporary database for each test."""
    db_path = tmp_path / "test_relic.db"
    init_db(db_path)
    yield db_path


@pytest.fixture
def db_connection(temp_db: Path) -> Generator[sqlite3.Connection, None, None]:
    """Provide a database connection to the temporary test database."""
    conn = get_connection(temp_db)
    try:
        yield conn
    finally:
        conn.close()
