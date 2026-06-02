"""
PR27M, Cross-Subject Aggregate Metrics Contract Tests

Tests verify:
- Cross-subject views show aggregate/redacted summaries only
- Private transcript side-by-side comparison is unavailable
- Cross-subject aggregates cannot mutate subject data
- Bulk identity/world/persona edit is unavailable
- Allowed aggregates: risk distribution, condition comparison, delivery volume, etc.
- Raw messages from multiple subjects are never shown
"""

import pytest
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "researcher-workbench" / "cross_subject_aggregate.json"


def load_fixture():
    import json
    with open(FIXTURE_PATH) as f:
        return json.load(f)


class TestCrossSubjectAggregateContract:
    """PR27M Cross-Subject Aggregate contract tests."""

    def test_cross_subject_views_aggregate_only(self):
        """Cross-subject views must show aggregate summaries only."""
        fixture = load_fixture()
        assert fixture.get("redacted") is True, "BLOCKED_CROSS_SUBJECT_RAW_MESSAGES"
        assert "aggregate_type" in fixture
        assert "data" in fixture

    def test_private_transcripts_unavailable(self):
        """Private transcript comparison must not be available."""
        fixture = load_fixture()
        # The aggregate must be redacted
        assert fixture.get("redacted") is True

    def test_cross_subject_cannot_mutate(self):
        """Cross-subject aggregates cannot mutate subject data."""
        fixture = load_fixture()
        # No mutation fields should be present
        assert "mutate" not in fixture
        assert "update" not in fixture
        assert "delete" not in fixture

    def test_bulk_persona_edit_unavailable(self):
        """Bulk persona/world/edit must not be available."""
        fixture = load_fixture()
        # No bulk edit fields
        assert "bulk_edit" not in fixture
        assert "bulk_persona_edit" not in fixture

    def test_aggregate_shows_risk_distribution(self):
        """Risk distribution aggregate must be available."""
        fixture = load_fixture()
        assert fixture["aggregate_type"] == "risk_distribution"
        assert "data" in fixture

    def test_aggregate_shows_condition_comparison(self):
        """Condition comparison aggregate must be available."""
        schema_path = Path(__file__).parent.parent.parent / "schemas" / "ui" / "cross_subject_aggregate.schema.json"
        import json
        with open(schema_path) as f:
            schema = json.load(f)
        allowed_types = schema["properties"]["aggregate_type"]["enum"]
        assert "condition_comparison" in allowed_types
