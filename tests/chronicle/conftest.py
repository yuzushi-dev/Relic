"""Chronicle test infrastructure, T016.

Provides shared fixtures for all Chronicle tests.
No other fixtures should be duplicated across test files.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Temp DB fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def tmp_relic_db() -> Generator[str, None, None]:
    """Creates a temporary SQLite database with all Chronicle migrations applied."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_chronicle.db")
        import sqlite3

        conn = sqlite3.connect(db_path)
        # Apply base schema
        base = Path(__file__).parent.parent.parent / "relic" / "db" / "migrations" / "0001_initial.sql"
        with open(base) as f:
            conn.executescript(f.read())
        # Apply Chronicle migrations
        for n, name in [
            ("0003", "chronicle_events"),
            ("0004", "chronicle_decisions"),
            ("0005", "chronicle_state_snapshots"),
            ("0006", "chronicle_provenance_edges"),
            ("0007", "chronicle_access_log"),
        ]:
            for suffix, table in [
                ("events", "chronicle_events"),
                ("decisions", "chronicle_decisions"),
                ("state_snapshots", "chronicle_state_snapshots"),
                ("provenance_edges", "chronicle_provenance_edges"),
                ("access_log", "chronicle_access_log"),
            ]:
                fpath = (
                    Path(__file__).parent.parent.parent
                    / "relic"
                    / "db"
                    / "migrations"
                    / f"{n}_chronicle_{suffix}.sql"
                )
                if fpath.exists():
                    with open(fpath) as sf:
                        conn.executescript(sf.read())
        conn.close()
        yield db_path


# ---------------------------------------------------------------------------
# Temp Chronicle dir fixture (JSONL journal path)
# ---------------------------------------------------------------------------
@pytest.fixture
def tmp_chronicle_dir() -> Generator[str, None, None]:
    """Creates a temporary ~/.relic/chronicle/ directory for JSONL journal tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        journal_dir = os.path.join(tmpdir, "journal")
        archive_dir = os.path.join(tmpdir, "archive")
        thinking_dir = os.path.join(tmpdir, "thinking")
        snapshots_dir = os.path.join(tmpdir, "snapshots")
        os.makedirs(journal_dir)
        os.makedirs(archive_dir)
        os.makedirs(thinking_dir)
        os.makedirs(snapshots_dir)
        yield tmpdir


# ---------------------------------------------------------------------------
# Default consent fail-open in test env (prod default = fail-closed)
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _chronicle_consent_test_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set CHRONICLE_CONSENT_FAIL_OPEN=1 by default in tests.

    Production default is fail-closed (deny capture on ConsentManager error).
    Tests assume the legacy fail-open behaviour unless they explicitly unset
    the env var via monkeypatch.delenv inside the test body.
    """
    monkeypatch.setenv("CHRONICLE_CONSENT_FAIL_OPEN", "1")


# ---------------------------------------------------------------------------
# Clean contextvars (reset trace_id/run_id/session_id for each test)
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def clean_contextvars() -> Generator[None, None, None]:
    """Resets Chronicle contextvars before and after each test."""
    # Import here to avoid circular issues before T011 is written
    try:
        from relic.chronicle import context as pctx

        pctx._trace_id.set(None)
        pctx._run_id.set(None)
        pctx._session_id.set(None)
        pctx._experiment_id.set(None)
    except ImportError:
        pass  # T011 not yet created, skip reset

    yield

    try:
        pctx._trace_id.set(None)
        pctx._run_id.set(None)
        pctx._session_id.set(None)
        pctx._experiment_id.set(None)
    except ImportError:
        pass


# ---------------------------------------------------------------------------
# Mock clock (freezegun wrap via simple time.time override)
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow tests to override time.time / datetime.utcnow for reproducible timestamps."""
    import time
    import datetime

    _frozen_time: float | None = None

    def frozen_time() -> float:
        if _frozen_time is not None:
            return _frozen_time
        return time.time()

    def frozen_now() -> datetime.datetime:
        return datetime.datetime.fromtimestamp(frozen_time(), tz=datetime.timezone.utc)

    monkeypatch.setattr(time, "time", frozen_time)
    monkeypatch.setattr(datetime, "datetime", type("FrozenDatetime", (), {
        "utcnow": staticmethod(frozen_now),
    }))


# ---------------------------------------------------------------------------
# Seed subject (consent record + sample subject_id for tests)
# ---------------------------------------------------------------------------
@pytest.fixture
def seed_subject(tmp_relic_db: str, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Seeds a subject with consent records and returns subject metadata."""
    import sqlite3

    subject_id = "test_subject_" + uuid.uuid4().hex[:8]
    session_id = str(uuid.uuid4())

    conn = sqlite3.connect(tmp_relic_db)
    conn.execute(
        "INSERT INTO consent_records (id, session_id, consent_type, granted, scope) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), session_id, "MEMORY_STORAGE", 1, "PERMANENT"),
    )
    conn.execute(
        "INSERT INTO consent_records (id, session_id, consent_type, granted, scope) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), session_id, "ANALYTICS", 1, "SESSION"),
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("REPLIC_RELIC_DB_PATH", tmp_relic_db)

    return {
        "subject_id": subject_id,
        "session_id": session_id,
        "consent_types": ["MEMORY_STORAGE", "ANALYTICS"],
    }


# ---------------------------------------------------------------------------
# Sample event (factory fixture)
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_event() -> dict[str, Any]:
    """Returns a minimal dict suitable for emit_event()."""
    return {
        "event_type": "test_event",
        "event_category": "background",
        "source_module": "tests.chronicle",
        "payload": {"test": True},
        "sensitivity": "safe",  # match PrivacyLevel enum value (lowercase)
    }


# ---------------------------------------------------------------------------
# Sample decision (factory fixture)
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_decision() -> dict[str, Any]:
    """Returns a minimal dict suitable for emit_decision()."""
    return {
        "decision_kind": "test_decision",
        "selected_action": {"action_type": "test", "action_ref": "test_ref"},
        "actor_type": "agent",
        "actor_id": "test_agent",
        "rationale_summary": "Test rationale for unit test.",
    }
