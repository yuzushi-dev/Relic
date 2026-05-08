"""PR26D — PR32 Sensitive Pattern Data Contract tests."""

import pytest
import json
import jsonschema


class TestPR32DataContract:
    """Test suite for PR32 sensitive pattern data contract."""

    @pytest.fixture
    def sensitive_signal_schema(self):
        """Load the sensitive signal schema."""
        schema_path = "schemas/data-model/sensitive_signal.schema.json"
        with open(schema_path, "r") as f:
            return json.load(f)

    @pytest.fixture
    def valid_signal(self):
        """Valid sensitive signal fixture."""
        return {
            "signal_id": "sig_001_a1b2c3d4",
            "subject_id": "subject_001",
            "gumi_instance_id": "gumi_instance_a1b2c3d4",
            "hermes_profile_id": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "signal_type": "family_mention_detected",
            "detected_at": "2024-01-15T14:30:00Z",
            "researcher_visible": True
        }

    def test_sensitive_signal_not_subject_visible(self, valid_signal, sensitive_signal_schema):
        """Sensitive signals must not be subject-visible."""
        signal = valid_signal.copy()
        signal["subject_visible"] = True
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(signal, sensitive_signal_schema)

    def test_sensitive_signal_not_gumi_visible(self, valid_signal, sensitive_signal_schema):
        """Sensitive signals must not be Gumi-visible."""
        signal = valid_signal.copy()
        signal["gumi_visible"] = True
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(signal, sensitive_signal_schema)

    def test_behavior_policy_patch_label_stripped(self, valid_signal, sensitive_signal_schema):
        """Behavior policy patches must have labels stripped."""
        signal = valid_signal.copy()
        signal["patch_applied"] = {
            "patch_delta": "some_patch",
            "labels_stripped": False  # Must be True
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(signal, sensitive_signal_schema)

    def test_sensitive_signal_requires_subject_scope(self, valid_signal, sensitive_signal_schema):
        """Sensitive signals require complete subject scope."""
        required_fields = ["subject_id", "gumi_instance_id", "hermes_profile_id"]
        for field in required_fields:
            signal = valid_signal.copy()
            del signal[field]
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate(signal, sensitive_signal_schema)

    def test_sensitive_signal_not_clinical_interpretation(self, valid_signal, sensitive_signal_schema):
        """Sensitive signals must not allow clinical interpretation."""
        signal = valid_signal.copy()
        signal["clinical_interpretation_allowed"] = True
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(signal, sensitive_signal_schema)
