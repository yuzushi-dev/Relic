"""Tests for artifact schemas validation.

These tests verify that:
- All artifact types have required zero-knowledge fields
- Schema validation enforces privacy constraints
- Artifacts cannot be emitted without correction_cutoff
- Artifacts cannot be emitted without source_snapshot_id
- Disputed/sensitive hints are properly tracked
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from relic.artifacts.types import (
    AgentEmbodimentPack,
    Artifact,
    ArtifactType,
    CorrectionCutoff,
    InteractionPolicyPack,
    LineageRef,
    RuntimeProfilePack,
    SchemaVersion,
    SourceSnapshotRef,
)


class TestSchemaVersion:
    """Tests for SchemaVersion type."""

    def test_schema_version_current(self):
        """Test SchemaVersion.current() returns correct version."""
        version = SchemaVersion.current()
        assert version.major == 1
        assert version.minor == 0
        assert version.patch == 0
        assert "runtime_profile_pack" in version.schema_uri

    def test_schema_version_str(self):
        """Test SchemaVersion string representation."""
        version = SchemaVersion(major=1, minor=2, patch=3, schema_uri="http://test")
        assert str(version) == "1.2.3"


class TestCorrectionCutoff:
    """Tests for CorrectionCutoff type."""

    def test_correction_cutoff_required_timestamp(self):
        """Test CorrectionCutoff requires cutoff_timestamp."""
        cutoff = CorrectionCutoff(cutoff_timestamp=datetime.utcnow())
        assert cutoff.cutoff_timestamp is not None
        assert cutoff.verified is False
        assert cutoff.corrections_applied == []

    def test_correction_cutoff_with_corrections(self):
        """Test CorrectionCutoff tracks applied corrections."""
        corr_ids = [uuid4(), uuid4()]
        cutoff = CorrectionCutoff(
            cutoff_timestamp=datetime.utcnow(),
            corrections_applied=corr_ids,
            corrections_pending=[],
            verified=True,
        )
        assert len(cutoff.corrections_applied) == 2
        assert cutoff.verified is True


class TestLineageRef:
    """Tests for LineageRef type."""

    def test_lineage_ref_creation(self):
        """Test LineageRef can be created."""
        parent_id = uuid4()
        ref = LineageRef(
            artifact_id=parent_id,
            artifact_type=ArtifactType.RUNTIME_PROFILE,
            relationship="derived_from",
        )
        assert ref.artifact_id == parent_id
        assert ref.artifact_type == ArtifactType.RUNTIME_PROFILE
        assert ref.relationship == "derived_from"


class TestSourceSnapshotRef:
    """Tests for SourceSnapshotRef type."""

    def test_source_snapshot_ref_creation(self):
        """Test SourceSnapshotRef can be created."""
        snapshot_id = uuid4()
        ref = SourceSnapshotRef(
            snapshot_id=snapshot_id,
            snapshot_type="session",
            content_hash="a" * 64,
        )
        assert ref.snapshot_id == snapshot_id
        assert ref.snapshot_type == "session"
        assert len(ref.content_hash) == 64


class TestBaseArtifact:
    """Tests for base Artifact type."""

    def test_artifact_requires_source_snapshot_id(self):
        """Test artifact cannot be emitted without source_snapshot_id."""
        artifact = Artifact(
            artifact_type=ArtifactType.RUNTIME_PROFILE,
            checksum="a" * 64,
            source_snapshot_id=None,
        )
        can_emit, reason = artifact.can_emit()
        assert can_emit is False
        assert "source_snapshot_id" in reason

    def test_artifact_requires_correction_cutoff(self):
        """Test artifact cannot be emitted without correction_cutoff."""
        artifact = Artifact(
            artifact_type=ArtifactType.RUNTIME_PROFILE,
            checksum="a" * 64,
            source_snapshot_id=uuid4(),
            correction_cutoff=None,
        )
        can_emit, reason = artifact.can_emit()
        assert can_emit is False
        assert "correction_cutoff" in reason

    def test_artifact_requires_lineage_refs_for_runtime_profile(self):
        """Test runtime_profile requires lineage_refs."""
        artifact = Artifact(
            artifact_type=ArtifactType.RUNTIME_PROFILE,
            checksum="a" * 64,
            source_snapshot_id=uuid4(),
            correction_cutoff=CorrectionCutoff(cutoff_timestamp=datetime.utcnow()),
            lineage_refs=[],
        )
        can_emit, reason = artifact.can_emit()
        assert can_emit is False
        assert "lineage_refs" in reason

    def test_artifact_can_emit_with_all_required_fields(self):
        """Test artifact can be emitted with all required fields."""
        parent_id = uuid4()
        artifact = Artifact(
            artifact_type=ArtifactType.AGENT_EMBODIMENT,
            checksum="a" * 64,
            source_snapshot_id=uuid4(),
            correction_cutoff=CorrectionCutoff(cutoff_timestamp=datetime.utcnow()),
            lineage_refs=[
                LineageRef(
                    artifact_id=parent_id,
                    artifact_type=ArtifactType.RUNTIME_PROFILE,
                    relationship="derived_from",
                )
            ],
        )
        can_emit, reason = artifact.can_emit()
        assert can_emit is True
        assert reason == ""

    def test_artifact_computes_content_checksum(self):
        """Test artifact can compute its content checksum."""
        artifact = Artifact(
            artifact_type=ArtifactType.INTERACTION_POLICY,
            checksum="a" * 64,
            source_snapshot_id=uuid4(),
            correction_cutoff=CorrectionCutoff(cutoff_timestamp=datetime.utcnow()),
        )
        checksum = artifact.compute_content_checksum()
        assert len(checksum) == 64
        assert checksum.isalnum()


class TestRuntimeProfilePack:
    """Tests for RuntimeProfilePack type."""

    def test_runtime_profile_requires_correction_cutoff(self):
        """Test RuntimeProfilePack requires correction_cutoff (validation error if None)."""
        # correction_cutoff is required field, passing None should raise ValidationError
        with pytest.raises(Exception):  # pydantic.ValidationError
            RuntimeProfilePack(
                checksum="a" * 64,
                source_snapshot_id=uuid4(),
                session_id=uuid4(),
                profile_type="session",
                prompt_hash="b" * 64,
                prompt_length=100,
                agent_id="test-agent",
                agent_version="1.0.0",
                correction_cutoff=None,  # This should fail validation
            )

    def test_runtime_profile_requires_lineage_refs(self):
        """Test RuntimeProfilePack requires lineage_refs for emission."""
        profile = RuntimeProfilePack(
            checksum="a" * 64,
            source_snapshot_id=uuid4(),
            session_id=uuid4(),
            profile_type="session",
            prompt_hash="b" * 64,
            prompt_length=100,
            agent_id="test-agent",
            agent_version="1.0.0",
            correction_cutoff=CorrectionCutoff(cutoff_timestamp=datetime.utcnow()),
            lineage_refs=[],
        )
        can_emit, reason = profile.can_emit()
        assert can_emit is False
        assert "lineage_refs" in reason

    def test_runtime_profile_can_emit(self):
        """Test RuntimeProfilePack can be emitted with all required fields."""
        profile = RuntimeProfilePack(
            checksum="a" * 64,
            source_snapshot_id=uuid4(),
            session_id=uuid4(),
            profile_type="session",
            prompt_hash="b" * 64,
            prompt_length=100,
            agent_id="test-agent",
            agent_version="1.0.0",
            correction_cutoff=CorrectionCutoff(cutoff_timestamp=datetime.utcnow()),
            lineage_refs=[
                LineageRef(
                    artifact_id=uuid4(),
                    artifact_type=ArtifactType.RUNTIME_PROFILE,
                    relationship="derived_from",
                )
            ],
        )
        can_emit, reason = profile.can_emit()
        assert can_emit is True

    def test_runtime_profile_no_raw_session_text(self):
        """Test RuntimeProfilePack has no field for raw session text."""
        model_fields = set(RuntimeProfilePack.model_fields.keys())
        assert "session_text" not in model_fields
        assert "raw_chat" not in model_fields
        assert "conversation" not in model_fields
        assert "prompt_hash" in model_fields

    def test_runtime_profile_tracks_hint_hashes(self):
        """Test RuntimeProfilePack tracks hint hashes, not actual hints."""
        hint_hashes = ["a" * 64, "b" * 64]
        profile = RuntimeProfilePack(
            checksum="a" * 64,
            source_snapshot_id=uuid4(),
            session_id=uuid4(),
            profile_type="session",
            prompt_hash="b" * 64,
            prompt_length=100,
            agent_id="test-agent",
            agent_version="1.0.0",
            hint_hashes=hint_hashes,
            disputed_hints_excluded=2,
            sensitive_hints_downgraded=1,
            correction_cutoff=CorrectionCutoff(cutoff_timestamp=datetime.utcnow()),
            lineage_refs=[],
        )
        assert len(profile.hint_hashes) == 2
        assert profile.disputed_hints_excluded == 2
        assert profile.sensitive_hints_downgraded == 1


class TestAgentEmbodimentPack:
    """Tests for AgentEmbodimentPack type."""

    def test_agent_embodiment_requires_correction_cutoff(self):
        """Test AgentEmbodimentPack requires correction_cutoff (validation error if None)."""
        with pytest.raises(Exception):  # pydantic.ValidationError
            AgentEmbodimentPack(
                checksum="a" * 64,
                source_snapshot_id=uuid4(),
                embodiment_type="text",
                capabilities=["text_generation"],
                constraints=["privacy_first"],
                correction_cutoff=None,
            )

    def test_agent_embodiment_can_emit(self):
        """Test AgentEmbodimentPack can be emitted with all required fields."""
        pack = AgentEmbodimentPack(
            checksum="a" * 64,
            source_snapshot_id=uuid4(),
            embodiment_type="text",
            capabilities=["text_generation", "reasoning"],
            constraints=["privacy_first", "no_harm"],
            correction_cutoff=CorrectionCutoff(cutoff_timestamp=datetime.utcnow()),
        )
        can_emit, reason = pack.can_emit()
        assert can_emit is True


class TestInteractionPolicyPack:
    """Tests for InteractionPolicyPack type."""

    def test_interaction_policy_requires_correction_cutoff(self):
        """Test InteractionPolicyPack requires correction_cutoff (validation error if None)."""
        with pytest.raises(Exception):  # pydantic.ValidationError
            InteractionPolicyPack(
                checksum="a" * 64,
                source_snapshot_id=uuid4(),
                policy_type="roleplay",
                rules=[],
                correction_cutoff=None,
            )

    def test_interaction_policy_can_emit(self):
        """Test InteractionPolicyPack can be emitted with all required fields."""
        pack = InteractionPolicyPack(
            checksum="a" * 64,
            source_snapshot_id=uuid4(),
            policy_type="factual",
            rules=[{"rule_id": "r1", "action": "allow", "condition": {}}],
            correction_cutoff=CorrectionCutoff(cutoff_timestamp=datetime.utcnow()),
        )
        can_emit, reason = pack.can_emit()
        assert can_emit is True


class TestJsonSchemaValidation:
    """Tests for JSON Schema validation."""

    @pytest.fixture
    def schemas_dir(self) -> Path:
        """Return path to schemas directory."""
        return Path(__file__).parent.parent.parent / "schemas"

    def test_runtime_profile_schema_exists(self, schemas_dir: Path):
        """Test runtime_profile_pack schema file exists."""
        schema_path = schemas_dir / "runtime_profile_pack.schema.json"
        assert schema_path.exists()

    def test_runtime_profile_schema_valid_json(self, schemas_dir: Path):
        """Test runtime_profile_pack schema is valid JSON."""
        schema_path = schemas_dir / "runtime_profile_pack.schema.json"
        with open(schema_path) as f:
            schema = json.load(f)
        assert "$schema" in schema
        assert "title" in schema
        assert "properties" in schema

    def test_runtime_profile_schema_requires_required_fields(self, schemas_dir: Path):
        """Test runtime_profile_pack schema requires mandatory fields."""
        schema_path = schemas_dir / "runtime_profile_pack.schema.json"
        with open(schema_path) as f:
            schema = json.load(f)
        required = schema.get("required", [])
        assert "id" in required
        assert "checksum" in required
        assert "source_snapshot_id" in required
        assert "correction_cutoff" in required
        assert "lineage_refs" in required
        assert "prompt_hash" in required

    def test_runtime_profile_schema_forbids_raw_session_text(self, schemas_dir: Path):
        """Test runtime_profile_pack schema has no raw session text fields."""
        schema_path = schemas_dir / "runtime_profile_pack.schema.json"
        with open(schema_path) as f:
            schema = json.load(f)
        properties = schema.get("properties", {})
        assert "session_text" not in properties
        assert "raw_chat" not in properties
        assert "conversation" not in properties
        assert "prompt_hash" in properties

    def test_runtime_profile_schema_checksum_pattern(self, schemas_dir: Path):
        """Test runtime_profile_pack schema enforces SHA-256 checksum pattern."""
        schema_path = schemas_dir / "runtime_profile_pack.schema.json"
        with open(schema_path) as f:
            schema = json.load(f)
        checksum_prop = schema["properties"]["checksum"]
        assert "pattern" in checksum_prop
        assert "^[a-f0-9]{64}$" in checksum_prop["pattern"]

    def test_agent_embodiment_schema_exists(self, schemas_dir: Path):
        """Test agent_embodiment_pack schema file exists."""
        schema_path = schemas_dir / "agent_embodiment_pack.schema.json"
        assert schema_path.exists()

    def test_interaction_policy_schema_exists(self, schemas_dir: Path):
        """Test interaction_policy_pack schema file exists."""
        schema_path = schemas_dir / "interaction_policy_pack.schema.json"
        assert schema_path.exists()

    def test_schemas_have_examples(self, schemas_dir: Path):
        """Test schemas include validation examples."""
        for schema_file in [
            "runtime_profile_pack.schema.json",
            "agent_embodiment_pack.schema.json",
            "interaction_policy_pack.schema.json",
        ]:
            schema_path = schemas_dir / schema_file
            with open(schema_path) as f:
                schema = json.load(f)
            assert "examples" in schema
            assert len(schema["examples"]) > 0
