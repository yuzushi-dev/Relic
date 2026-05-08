"""Tests for relic database schema."""

from __future__ import annotations

import tempfile
from pathlib import Path

from relic.db import get_connection, init_db


def test_init_db_creates_tables():
    """Database initialization creates all required tables."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        init_db(db_path)
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in cursor.fetchall()}
            assert "schema_version" in tables
            assert "prompt_records" in tables
            assert "correction_records" in tables
            assert "artifact_records" in tables
            assert "consent_records" in tables
        finally:
            conn.close()


def test_schema_version_recorded():
    """Initial schema version is recorded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        init_db(db_path)
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT version FROM schema_version")
            versions = cursor.fetchall()
            assert len(versions) > 0
            assert "0001" in [v[0] for v in versions]
        finally:
            conn.close()


def test_prompt_records_has_lineage():
    """Prompt records table has lineage columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        init_db(db_path)
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(prompt_records)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "id" in columns
            assert "created_at" in columns
            assert "updated_at" in columns
        finally:
            conn.close()


def test_prompt_records_privacy_safe():
    """Prompt records stores content hash, not raw content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        init_db(db_path)
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(prompt_records)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "content_hash" in columns
            assert "content_length" in columns
            assert "is_redacted" in columns
            assert "content" not in columns
        finally:
            conn.close()


def test_artifact_registry_exists():
    """Artifact registry table exists with proper columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        init_db(db_path)
        conn = get_connection(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(artifact_records)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "id" in columns
            assert "session_id" in columns
            assert "artifact_type" in columns
            assert "artifact_hash" in columns
            assert "lineage_path" in columns
            assert "metadata_json" in columns
        finally:
            conn.close()
