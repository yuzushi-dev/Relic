"""PR28, Identity schema contract tests."""

import json
import pytest
from pathlib import Path
from jsonschema import validate, ValidationError

SCHEMA_PATH = Path(__file__).parent.parent.parent / "schemas" / "identity" / "gumi_identity_consistency_event.schema.json"


class TestIdentitySchemaContract:
    """Schema contract tests for identity consistency events."""

    def test_schema_loads(self):
        """Schema file loads as valid JSON."""
        with open(SCHEMA_PATH) as f:
            schema = json.load(f)
        assert "$schema" in schema
        assert schema["type"] == "object"

    def test_prompt_variant_enum_valid(self):
        """Schema defines valid prompt_variant options."""
        with open(SCHEMA_PATH) as f:
            schema = json.load(f)
        variants = schema["properties"]["prompt_variant"]["enum"]
        assert "original" in variants
        assert "paraphrase_01" in variants
        assert "control_generic" in variants

    def test_consistency_score_is_number(self):
        """consistency_score is numeric type."""
        with open(SCHEMA_PATH) as f:
            schema = json.load(f)
        assert schema["properties"]["consistency_score"]["type"] == "number"

    def test_identity_markers_is_array(self):
        """identity_markers_detected is an array of strings."""
        with open(SCHEMA_PATH) as f:
            schema = json.load(f)
        assert schema["properties"]["identity_markers_detected"]["type"] == "array"
        assert schema["properties"]["identity_markers_detected"]["items"]["type"] == "string"
