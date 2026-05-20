"""Tests for delete functionality with dry-run.

Acceptance criteria:
- delete dry-run lists affected artifacts
- delete apply invalidates derived artifacts
"""

from __future__ import annotations

from uuid import uuid4

from relic.control.delete import DeleteManager, DeleteScope
from relic.db import get_cursor


class TestDeleteDryRun:
    """Tests for delete dry-run functionality."""

    def test_dry_run_all_scope(self, temp_db):
        """Test dry-run for all scope."""
        manager = DeleteManager(db_path=str(temp_db))

        result = manager.dry_run(scope=DeleteScope.ALL)

        assert result.scope == DeleteScope.ALL
        assert result.target_id is None

    def test_dry_run_lists_affected_artifacts(self, temp_db):
        """Test that dry-run lists affected artifacts."""
        session_id = uuid4()

        with get_cursor(str(temp_db)) as cur:
            cur.execute(
                """
                INSERT INTO artifact_records
                (id, session_id, artifact_type, artifact_hash, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    str(session_id),
                    "response",
                    "hash123",
                    '{"derived": true}',
                ),
            )

        manager = DeleteManager(db_path=str(temp_db))
        result = manager.dry_run(scope=DeleteScope.SESSION, target_id=session_id)

        assert len(result.affected_artifacts) == 1
        assert result.affected_artifacts[0].session_id == session_id

    def test_dry_run_includes_replication_bundles(self, temp_db):
        """Test dry-run includes replication bundle count."""
        with get_cursor(str(temp_db)) as cur:
            cur.execute(
                """
                INSERT INTO artifact_records
                (id, session_id, artifact_type, artifact_hash, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    str(uuid4()),
                    "bundle",
                    "hash456",
                    '{"replication_bundle": true}',
                ),
            )

        manager = DeleteManager(db_path=str(temp_db))
        result = manager.dry_run(scope=DeleteScope.ALL)

        assert result.affected_replication_bundles >= 1

    def test_dry_run_includes_eval_cases(self, temp_db):
        """Test dry-run includes eval case count."""
        with get_cursor(str(temp_db)) as cur:
            cur.execute(
                """
                INSERT INTO artifact_records
                (id, session_id, artifact_type, artifact_hash, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    str(uuid4()),
                    "eval",
                    "hash789",
                    '{"eval_case": true}',
                ),
            )

        manager = DeleteManager(db_path=str(temp_db))
        result = manager.dry_run(scope=DeleteScope.ALL)

        assert result.affected_eval_cases >= 1


class TestDeleteApply:
    """Tests for delete apply functionality."""

    def test_delete_invalidates_artifacts(self, temp_db):
        """Test that delete apply invalidates derived artifacts."""
        session_id = uuid4()
        artifact_id = uuid4()

        with get_cursor(str(temp_db)) as cur:
            cur.execute(
                """
                INSERT INTO artifact_records
                (id, session_id, artifact_type, artifact_hash, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(artifact_id),
                    str(session_id),
                    "response",
                    "hash123",
                    '{"derived": true}',
                ),
            )

        manager = DeleteManager(db_path=str(temp_db))
        result = manager.delete(scope=DeleteScope.SESSION, target_id=session_id)

        assert result.deleted_artifacts >= 1

        with get_cursor(str(temp_db)) as cur:
            cur.execute(
                "SELECT metadata_json FROM artifact_records WHERE id = ?",
                (str(artifact_id),),
            )
            row = cur.fetchone()
            assert "invalidated" in row["metadata_json"]

    def test_delete_invalidates_replication_bundles(self, temp_db):
        """Test that delete invalidates replication bundles."""
        with get_cursor(str(temp_db)) as cur:
            cur.execute(
                """
                INSERT INTO artifact_records
                (id, session_id, artifact_type, artifact_hash, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    str(uuid4()),
                    "bundle",
                    "hash456",
                    '{"replication_bundle": true}',
                ),
            )

        manager = DeleteManager(db_path=str(temp_db))
        result = manager.delete(scope=DeleteScope.ALL)

        assert result.invalidated_replication_bundles >= 1

    def test_delete_invalidates_eval_cases(self, temp_db):
        """Test that delete invalidates eval cases."""
        with get_cursor(str(temp_db)) as cur:
            cur.execute(
                """
                INSERT INTO artifact_records
                (id, session_id, artifact_type, artifact_hash, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    str(uuid4()),
                    "eval",
                    "hash789",
                    '{"eval_case": true}',
                ),
            )

        manager = DeleteManager(db_path=str(temp_db))
        result = manager.delete(scope=DeleteScope.ALL)

        assert result.invalidated_eval_cases >= 1

    def test_delete_prompt_scope(self, temp_db):
        """Test deleting a single prompt."""
        prompt_id = uuid4()
        session_id = uuid4()

        with get_cursor(str(temp_db)) as cur:
            cur.execute(
                """
                INSERT INTO prompt_records
                (id, session_id, role, content_hash, content_length, is_redacted)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(prompt_id), str(session_id), "user", "hashabc", 100, False),
            )

        manager = DeleteManager(db_path=str(temp_db))
        result = manager.delete(scope=DeleteScope.PROMPT, target_id=prompt_id)

        assert result.deleted_prompts == 1

        with get_cursor(str(temp_db)) as cur:
            cur.execute("SELECT * FROM prompt_records WHERE id = ?", (str(prompt_id),))
            row = cur.fetchone()
            assert row is None

    def test_delete_session_scope(self, temp_db):
        """Test deleting all prompts in a session."""
        session_id = uuid4()
        prompt_a = uuid4()
        prompt_b = uuid4()

        with get_cursor(str(temp_db)) as cur:
            cur.execute(
                """
                INSERT INTO prompt_records
                (id, session_id, role, content_hash, content_length, is_redacted)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(prompt_a), str(session_id), "user", "hash1", 100, False),
            )
            cur.execute(
                """
                INSERT INTO prompt_records
                (id, session_id, role, content_hash, content_length, is_redacted)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(prompt_b), str(session_id), "assistant", "hash2", 200, False),
            )

        manager = DeleteManager(db_path=str(temp_db))
        result = manager.delete(scope=DeleteScope.SESSION, target_id=session_id)

        assert result.deleted_prompts == 2

    def test_delete_session_scope_deletes_prompt_corrections(self, temp_db):
        """Session delete removes corrections before deleting their prompts."""
        session_id = uuid4()
        prompt_id = uuid4()
        correction_id = uuid4()

        with get_cursor(str(temp_db)) as cur:
            cur.execute(
                """
                INSERT INTO prompt_records
                (id, session_id, role, content_hash, content_length, is_redacted)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(prompt_id), str(session_id), "user", "hash1", 100, False),
            )
            cur.execute(
                """
                INSERT INTO correction_records
                (id, prompt_id, correction_type, delta_content, applied, source)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(correction_id), str(prompt_id), "redaction", "{}", False, "manual"),
            )

        manager = DeleteManager(db_path=str(temp_db))
        result = manager.delete(scope=DeleteScope.SESSION, target_id=session_id)

        assert result.deleted_prompts == 1
        assert result.deleted_corrections == 1

        with get_cursor(str(temp_db)) as cur:
            row = cur.execute(
                "SELECT * FROM correction_records WHERE id = ?",
                (str(correction_id),),
            ).fetchone()
            assert row is None
