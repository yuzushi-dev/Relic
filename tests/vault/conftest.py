"""Pytest configuration for vault tests."""

import pytest

from relic.db import init_db


@pytest.fixture(autouse=True)
def reset_db(tmp_path, monkeypatch):
    """Reset database for each test using temp path."""
    import relic.paths as paths

    test_db = tmp_path / "test_vault.db"
    monkeypatch.setattr(paths, "get_db_path", lambda: test_db)

    init_db(test_db)

    yield test_db
