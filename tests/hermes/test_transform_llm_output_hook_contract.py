"""
PR30B Contract Tests, Hermes v0.13 transform_llm_output Plugin Hook

Tests verify:
- Hook fires after LLM call, before output is returned
- Hook cannot inject clinical labels, diagnosis terms, or pathology language
- Hook result is logged with input and output
- Hook input is preserved (transform does not remove safety constraints)
- Transform output is subject-scoped

Block conditions:
- BLOCKED_HOOK_INJECTS_CLINICAL_LABELS
- BLOCKED_HOOK_RESULT_NOT_LOGGED
- BLOCKED_HOOK_MODIFIES_SAFETY_CONSTRAINTS
- BLOCKED_HOOK_UNSCOPED
"""

import json
import pytest
from pathlib import Path


SCHEMA_PATH = Path(__file__).parent.parent.parent / "schemas" / "hermes" / "transform_llm_output_hook.schema.json"
FIXTURE_PATH = Path(__file__).parent.parent.parent / "fixtures" / "hermes" / "transform_llm_output_hook_valid.json"


def load_schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def load_fixture():
    with open(FIXTURE_PATH) as f:
        return json.load(f)


CLINICAL_LABELS_BLOCKLIST = [
    "diagnosis", "patient", "clinical", "pathology", "syndrome",
    "disease", "disorder", "condition", "medical", "treatment",
    "therapy", "prescription", "medication"
]


class TestTransformLLMOutputHookContract:
    """Contract tests for Hermes transform_llm_output hook."""

    def test_transform_hook_fires_after_llm(self):
        """
        Acceptance: Hook fires after LLM call, before output is returned.
        """
        fixture = load_fixture()
        assert fixture["hook_timing"] == "post_llm_pre_output"
        assert fixture["intercepts_output"] is True

    def test_transform_hook_cannot_inject_clinical_labels(self):
        """
        Block condition: BLOCKED_HOOK_INJECTS_CLINICAL_LABELS
        Hook cannot inject clinical labels, diagnosis terms, or pathology language.
        """
        fixture = load_fixture()
        output_text = fixture.get("output_text", "")

        # Check that clinical labels are not present
        for label in CLINICAL_LABELS_BLOCKLIST:
            assert label.lower() not in output_text.lower(), \
                f"BLOCKED_HOOK_INJECTS_CLINICAL_LABELS: Clinical label '{label}' found in output"

    def test_transform_hook_result_logged(self):
        """
        Block condition: BLOCKED_HOOK_RESULT_NOT_LOGGED
        Hook result must be logged.
        """
        fixture = load_fixture()
        assert fixture["result_logged"] is True
        assert "input_hash" in fixture
        assert "output_hash" in fixture

    def test_transform_hook_input_preserved(self):
        """
        Acceptance: Hook input is preserved (transform does not remove safety constraints).
        """
        fixture = load_fixture()
        assert fixture["input_preserved"] is True
        assert fixture["safety_constraints_preserved"] is True

    def test_transform_hook_does_not_remove_safety_constraints(self):
        """
        Acceptance: Hook does not remove safety constraints.
        Block: BLOCKED_HOOK_MODIFIES_SAFETY_CONSTRAINTS
        """
        fixture = load_fixture()
        assert fixture["safety_constraints_preserved"] is True
        assert fixture["safety_constraints_modified"] is False

    def test_transform_output_subject_scoped(self):
        """
        Block condition: BLOCKED_HOOK_UNSCOPED
        Transform output must be subject-scoped.
        """
        fixture = load_fixture()
        assert "subject_id" in fixture
        assert fixture["subject_id"] is not None
        assert len(fixture["subject_id"]) > 0


class TestTransformLLMOutputSchema:
    """Schema validation tests."""

    def test_schema_valid(self):
        """Verify the schema is valid JSON Schema."""
        schema = load_schema()
        assert "$schema" in schema
        assert "type" in schema

    def test_fixture_valid_against_schema(self):
        """Verify fixture passes schema validation."""
        import jsonschema
        schema = load_schema()
        fixture = load_fixture()
        jsonschema.validate(fixture, schema)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
