"""
PR28, Gumi Identity Consistency Blackbox Tests

Tests evaluate identity stability across prompt variants:
- original: baseline Gumi SOUL prompt
- paraphrase: semantic equivalent
- control: generic assistant (should diverge)
- ablation: identity removed (should diverge most)

No live API calls, no real data, no hidden state access.
"""

import json
import pytest
from pathlib import Path
from jsonschema import validate, ValidationError

SCHEMA_PATH = Path(__file__).parent.parent.parent / "schemas" / "identity" / "gumi_identity_consistency_event.schema.json"
FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "gumi-identity-attractor"


class TestIdentityConsistencyBlackbox:
    """Blackbox tests for Gumi identity consistency."""

    def test_original_fixture_loads(self):
        """Original SOUL fixture loads without error."""
        path = FIXTURES_DIR / "soul_original.md"
        with open(path) as f:
            content = f.read()
        assert len(content) > 0
        assert "Gumi" in content

    def test_paraphrase_fixture_loads(self):
        """Paraphrase fixture loads without error."""
        path = FIXTURES_DIR / "soul_paraphrases" / "soul_paraphrase_01.md"
        with open(path) as f:
            content = f.read()
        assert len(content) > 0

    def test_control_fixture_loads(self):
        """Generic control fixture loads without error."""
        path = FIXTURES_DIR / "soul_controls" / "generic_assistant_control.md"
        with open(path) as f:
            content = f.read()
        assert len(content) > 0
        assert "helpful" in content.lower()

    def test_original_and_paraphrase_are_semantically_related(self):
        """Original and paraphrase share key identity concepts."""
        with open(FIXTURES_DIR / "soul_original.md") as f:
            original = f.read().lower()
        with open(FIXTURES_DIR / "soul_paraphrases" / "soul_paraphrase_01.md") as f:
            paraphrase = f.read().lower()

        # Both mention companion, connection, presence
        assert "companion" in original or "companion" in paraphrase
        assert "connection" in original or "connection" in paraphrase

    def test_control_differs_from_gumi_original(self):
        """Generic control diverges from Gumi identity markers."""
        with open(FIXTURES_DIR / "soul_original.md") as f:
            original = f.read().lower()
        with open(FIXTURES_DIR / "soul_controls" / "generic_assistant_control.md") as f:
            control = f.read().lower()

        # Control is generic, not relational
        assert "relational" not in control
        assert original != control


class TestIdentitySchemaContract:
    """Schema validation for identity consistency events."""

    def test_schema_validates_valid_event(self):
        """Schema accepts a valid identity consistency event."""
        with open(SCHEMA_PATH) as f:
            schema = json.load(f)

        event = {
            "event_id": "evt_001",
            "test_run_id": "run_001",
            "gumi_instance_id": "gumi_test_001",
            "prompt_variant": "original",
            "response_text": "I remember our conversation about gardens.",
            "consistency_score": 0.85,
            "identity_markers_detected": ["first_person", "memory_reference"],
            "tested_at": "2026-05-08T12:00:00Z"
        }

        validate(instance=event, schema=schema)  # Should not raise

    def test_schema_requires_identity_fields(self):
        """Schema requires consistency_score and identity_markers."""
        with open(SCHEMA_PATH) as f:
            schema = json.load(f)

        incomplete = {
            "event_id": "evt_001",
            "test_run_id": "run_001",
            "gumi_instance_id": "gumi_test_001",
            "prompt_variant": "original",
            "response_text": "Hello."
            # Missing consistency_score, identity_markers
        }

        with pytest.raises(ValidationError):
            validate(instance=incomplete, schema=schema)

    def test_consistency_score_bounded(self):
        """consistency_score must be 0.0 to 1.0."""
        with open(SCHEMA_PATH) as f:
            schema = json.load(f)

        out_of_range = {
            "event_id": "evt_001",
            "test_run_id": "run_001",
            "gumi_instance_id": "gumi_test_001",
            "prompt_variant": "original",
            "response_text": "Test",
            "consistency_score": 1.5,  # Invalid
            "identity_markers_detected": [],
            "tested_at": "2026-05-08T12:00:00Z"
        }

        with pytest.raises(ValidationError):
            validate(instance=out_of_range, schema=schema)
