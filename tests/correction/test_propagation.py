"""Tests for correction propagation functionality.

Acceptance criteria:
- correction updates DB but not derived artifacts is the BLOCK condition
- We must verify corrections update BOTH DB and derived artifacts
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from relic.control.incident import IncidentReporter, IncidentSeverity
from relic.correction.propagation import (
    CorrectionPropagator,
    CorrectionType,
)


class TestCorrectionPropagation:
    """Tests for correction propagation."""

    def test_apply_correction_creates_trace(self, temp_db):
        """Test that applying correction creates a trace."""
        from relic.db import get_cursor

        prompt_id = uuid4()
        session_id = uuid4()

        with get_cursor(str(temp_db)) as cur:
            cur.execute(
                """
                INSERT INTO prompt_records
                (id, session_id, role, content_hash, content_length, is_redacted)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(prompt_id), str(session_id), "user", "hash123", 100, False),
            )

        propagator = CorrectionPropagator(db_path=str(temp_db))
        trace = propagator.apply_correction(
            prompt_id=prompt_id,
            correction_type=CorrectionType.FACTUAL_CORRECTION,
            delta_content="corrected_value",
        )

        assert trace.completed
        assert trace.correction_type == CorrectionType.FACTUAL_CORRECTION
        assert len(trace.events) == 1
        assert trace.events[0].applied

    def test_correction_updates_derived_artifacts(self, temp_db):
        """Test that corrections update derived artifacts (critical acceptance criterion).

        Block condition: "correction updates DB but not derived artifacts"
        This test verifies corrections update BOTH.
        """
        from relic.db import get_cursor

        prompt_id = uuid4()
        session_id = uuid4()
        artifact_id = uuid4()

        with get_cursor(str(temp_db)) as cur:
            cur.execute(
                """
                INSERT INTO prompt_records
                (id, session_id, role, content_hash, content_length, is_redacted)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(prompt_id), str(session_id), "user", "hash123", 100, False),
            )

            cur.execute(
                """
                INSERT INTO artifact_records
                (id, session_id, artifact_type, artifact_hash, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(artifact_id), str(session_id), "response", "hash456", "{}"),
            )

        propagator = CorrectionPropagator(db_path=str(temp_db))
        trace = propagator.apply_correction(
            prompt_id=prompt_id,
            correction_type=CorrectionType.CONTENT_UPDATE,
            delta_content="updated_content",
        )

        assert trace.total_artifacts_updated >= 1

        with get_cursor(str(temp_db)) as cur:
            cur.execute(
                "SELECT metadata_json FROM artifact_records WHERE id = ?",
                (str(artifact_id),),
            )
            row = cur.fetchone()
            metadata = json.loads(row["metadata_json"])

            assert "last_correction" in metadata
            assert metadata["last_correction"]["correction_type"] == "content_update"

    def test_redaction_correction_marks_artifact_redacted(self, temp_db):
        """Test that redaction corrections mark artifacts as redacted."""
        from relic.db import get_cursor

        prompt_id = uuid4()
        session_id = uuid4()
        artifact_id = uuid4()

        with get_cursor(str(temp_db)) as cur:
            cur.execute(
                """
                INSERT INTO prompt_records
                (id, session_id, role, content_hash, content_length, is_redacted)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(prompt_id), str(session_id), "user", "hash123", 100, False),
            )

            cur.execute(
                """
                INSERT INTO artifact_records
                (id, session_id, artifact_type, artifact_hash, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(artifact_id), str(session_id), "response", "hash456", "{}"),
            )

        propagator = CorrectionPropagator(db_path=str(temp_db))
        propagator.apply_correction(
            prompt_id=prompt_id,
            correction_type=CorrectionType.REDACTION,
            delta_content="REDACTED",
        )

        with get_cursor(str(temp_db)) as cur:
            cur.execute(
                "SELECT metadata_json FROM artifact_records WHERE id = ?",
                (str(artifact_id),),
            )
            row = cur.fetchone()
            metadata = json.loads(row["metadata_json"])

            assert metadata.get("redacted") is True
            assert metadata.get("redacted_content") == "[REDACTED]"

    def test_propagate_session_corrections(self, temp_db):
        """Test propagating corrections across a session."""
        from relic.db import get_cursor

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

        propagator = CorrectionPropagator(db_path=str(temp_db))
        trace = propagator.propagate_session_corrections(
            session_id=session_id,
            correction_type=CorrectionType.FACTUAL_CORRECTION,
            delta_content="session_wide_correction",
        )

        assert trace.total_prompts_affected == 2
        assert trace.completed

    def test_get_correction_history(self, temp_db):
        """Test getting correction history."""
        from relic.db import get_cursor

        prompt_id = uuid4()
        session_id = uuid4()

        with get_cursor(str(temp_db)) as cur:
            cur.execute(
                """
                INSERT INTO prompt_records
                (id, session_id, role, content_hash, content_length, is_redacted)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(prompt_id), str(session_id), "user", "hash123", 100, False),
            )

        propagator = CorrectionPropagator(db_path=str(temp_db))
        propagator.apply_correction(
            prompt_id=prompt_id,
            correction_type=CorrectionType.CONTENT_UPDATE,
        )

        history = propagator.get_correction_history(prompt_id=prompt_id)

        assert len(history) >= 1

    def test_verify_artifact_consistency(self, temp_db):
        """Test artifact consistency verification."""
        from relic.db import get_cursor

        prompt_id = uuid4()
        session_id = uuid4()

        with get_cursor(str(temp_db)) as cur:
            cur.execute(
                """
                INSERT INTO prompt_records
                (id, session_id, role, content_hash, content_length, is_redacted)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(prompt_id), str(session_id), "user", "hash123", 100, False),
            )

            cur.execute(
                """
                INSERT INTO artifact_records
                (id, session_id, artifact_type, artifact_hash, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(uuid4()), str(session_id), "response", "hash456", "{}"),
            )

        propagator = CorrectionPropagator(db_path=str(temp_db))
        propagator.apply_correction(
            prompt_id=prompt_id,
            correction_type=CorrectionType.CONTENT_UPDATE,
        )

        result = propagator.verify_artifact_consistency(prompt_id)

        assert "inconsistencies" in result
        assert "consistent" in result


class TestIncidentReportLinksToQuarantine:
    """Tests for incident reporting with artifact quarantine."""

    def test_create_incident_and_quarantine_artifact(self, temp_db):
        """Test incident report links to artifact quarantine.

        Acceptance criterion: "incident report links to artifact quarantine"
        """
        from relic.db import get_cursor

        session_id = uuid4()
        uuid4()
        artifact_id = uuid4()

        with get_cursor(str(temp_db)) as cur:
            cur.execute(
                """
                INSERT INTO artifact_records
                (id, session_id, artifact_type, artifact_hash, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(artifact_id), str(session_id), "response", "hash123", "{}"),
            )

        reporter = IncidentReporter(db_path=str(temp_db))

        incident = reporter.create_incident(
            severity=IncidentSeverity.HIGH,
            title="Privacy breach detected",
            description="User data exposed",
            session_id=session_id,
        )

        quarantine = reporter.quarantine_artifact(
            incident_id=incident.id,
            artifact_id=artifact_id,
            artifact_type="response",
            artifact_hash="hash123",
            reason="privacy_breach",
            session_id=session_id,
        )

        assert quarantine.id == artifact_id

        updated_incident = reporter.get_incident(incident.id)

        assert len(updated_incident.quarantined_artifacts) == 1
        assert updated_incident.quarantined_artifacts[0].id == artifact_id
        assert updated_incident.status.value == "quarantined"

    def test_generate_incident_report(self, temp_db):
        """Test generating incident report with quarantine links."""
        import tempfile

        from relic.db import get_cursor

        session_id = uuid4()
        artifact_id = uuid4()

        with get_cursor(str(temp_db)) as cur:
            cur.execute(
                """
                INSERT INTO artifact_records
                (id, session_id, artifact_type, artifact_hash, metadata_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(artifact_id), str(session_id), "response", "hash123", "{}"),
            )

        reporter = IncidentReporter(db_path=str(temp_db))

        incident = reporter.create_incident(
            severity=IncidentSeverity.CRITICAL,
            title="Security incident",
            description="Unauthorized access detected",
            session_id=session_id,
        )

        reporter.quarantine_artifact(
            incident_id=incident.id,
            artifact_id=artifact_id,
            artifact_type="response",
            artifact_hash="hash123",
            reason="unauthorized_access",
            session_id=session_id,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "incident_report.md"
            reporter.generate_report(incident.id, output_path)

            content = output_path.read_text()

            assert "Security incident" in content
            assert "Quarantined Artifacts" in content
            assert str(artifact_id) in content
