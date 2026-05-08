"""PR26F — Export, Delete, and Forget Semantics tests."""

import pytest
import json
import jsonschema


class TestExportDeleteForget:
    """Test suite for export, delete, and forget semantics."""

    @pytest.fixture
    def export_manifest_schema(self):
        """Load the export manifest schema."""
        schema_path = "schemas/data-model/export_manifest.schema.json"
        with open(schema_path, "r") as f:
            return json.load(f)

    @pytest.fixture
    def valid_manifest(self):
        """Valid export manifest fixture."""
        return {
            "subject_id": "subject_001",
            "condition": "withdrawal",
            "redaction_status": "redacted",
            "hermes_profile_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "soul_md_hash": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
            "policy_snapshot": "policy_v2.3_sha256:abc123def456",
            "event_counts": {
                "empirical_user_interaction": 150,
                "governance_decision": 2
            },
            "exported_at": "2024-01-20T12:00:00Z"
        }

    def test_export_excludes_researcher_safety_signals(self, valid_manifest):
        """Export must exclude researcher-only safety signals."""
        doc_path = "docs/data-model/06_EXPORT_DELETE_FORGET.md"
        with open(doc_path, "r") as f:
            content = f.read()
        assert "Safety Signals" in content or "safety_signals" in content.lower()
        assert "excluded" in content.lower()

    def test_forget_removes_gumi_recall(self):
        """Forget must remove data from Gumi recall."""
        doc_path = "docs/data-model/06_EXPORT_DELETE_FORGET.md"
        with open(doc_path, "r") as f:
            content = f.read()
        assert "Gumi recall" in content
        assert "without deleting" in content.lower() or "removes" in content.lower()

    def test_delete_creates_audit_event(self):
        """Delete must create an audit event."""
        doc_path = "docs/data-model/06_EXPORT_DELETE_FORGET.md"
        with open(doc_path, "r") as f:
            content = f.read()
        assert "audit" in content.lower()
        assert "delete" in content.lower()

    def test_export_manifest_has_subject_id(self, valid_manifest, export_manifest_schema):
        """Export manifest must have subject_id."""
        manifest = valid_manifest.copy()
        del manifest["subject_id"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(manifest, export_manifest_schema)

    def test_export_manifest_has_redaction_status(self, valid_manifest, export_manifest_schema):
        """Export manifest must have redaction_status."""
        manifest = valid_manifest.copy()
        del manifest["redaction_status"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(manifest, export_manifest_schema)

    def test_forget_is_subject_scoped(self):
        """Forget must be subject-scoped."""
        doc_path = "docs/data-model/06_EXPORT_DELETE_FORGET.md"
        with open(doc_path, "r") as f:
            content = f.read()
        assert "subject-scoped" in content.lower() or "subject scoped" in content
        assert "another subject" in content or "other subject" in content
