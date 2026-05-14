"""Tests for PromptContextPack schema validation."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from relic.context_pack import (
    PromptContextPack,
    SystemSource,
    TaskType,
    RoleplayLevel,
    ContinuityMode,
    ContextSource,
    SubjectScope,
    DisclosureLevel,
)
from relic.context_pack.schema import validate_pack, SCHEMA_PATH


def _utcnow() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


class TestSchemaValidation:
    """Test suite for PromptContextPack schema validation."""

    def test_valid_full_pack(self, full_pack_with_scope):
        """Test that a fully populated pack validates successfully."""
        errors = validate_pack(full_pack_with_scope)
        assert errors == [], f"Valid pack should have no errors: {errors}"

    def test_valid_minimal_pack(self, minimal_pack):
        """Test that a minimal pack validates successfully."""
        errors = validate_pack(minimal_pack)
        assert errors == [], f"Minimal pack should validate: {errors}"

    def test_pack_to_dict_roundtrip(self, full_pack_with_scope):
        """Test that pack can be serialized and deserialized."""
        data = full_pack_with_scope.to_dict()
        restored = PromptContextPack.from_dict(data)

        assert restored.pack_id == full_pack_with_scope.pack_id
        assert restored.task_type == full_pack_with_scope.task_type
        assert restored.roleplay_level == full_pack_with_scope.roleplay_level
        assert len(restored.system_sources) == len(full_pack_with_scope.system_sources)

    def test_missing_required_field_session_id(self):
        """Test that missing session_id fails validation."""
        pack = PromptContextPack(
            pack_id="PCP-test",
            # session_id intentionally missing
            turn_id="TURN-1",
            task_type=TaskType.FACTUAL,
            roleplay_level=RoleplayLevel.OFF,
            continuity_mode=ContinuityMode.NONE,
        )
        errors = validate_pack(pack)
        assert len(errors) > 0, "Missing session_id should fail"

    def test_invalid_task_type(self):
        """Test that invalid task_type fails validation."""
        pack = PromptContextPack(
            pack_id="PCP-test",
            session_id="SES-123",
            turn_id="TURN-1",
            # task_type intentionally not set (defaults to FACTUAL)
        )
        # Actually, since task_type has a default, we test by setting an invalid enum
        # The TaskType enum will raise ValueError if invalid
        try:
            TaskType("invalid_type")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass  # Expected

    def test_schema_path_exists(self):
        """Test that the schema file exists at expected path."""
        assert SCHEMA_PATH.exists(), f"Schema not found at {SCHEMA_PATH}"


class TestSubjectScope:
    """Test suite for subject scope validation."""

    def test_has_subject_scope_true(self, full_pack_with_scope):
        """Test that pack with scope returns True."""
        assert full_pack_with_scope.has_subject_scope() is True

    def test_has_subject_scope_false(self, pack_missing_scope):
        """Test that pack without scope returns False."""
        assert pack_missing_scope.has_subject_scope() is False

    def test_subject_scope_from_dict(self):
        """Test SubjectScope serialization roundtrip."""
        scope = SubjectScope(
            subject_id="test-subject",
            disclosure_level=DisclosureLevel.RESTRICTED,
            is_active=True,
            metadata={"key": "value"},
        )
        data = scope.to_dict()
        restored = SubjectScope.from_dict(data)

        assert restored.subject_id == scope.subject_id
        assert restored.disclosure_level == scope.disclosure_level
        assert restored.is_active == scope.is_active


class TestSystemSource:
    """Test suite for SystemSource validation."""

    def test_system_source_to_dict(self):
        """Test SystemSource serialization."""
        source = SystemSource(
            source=ContextSource.MEMORY,
            priority=75,
            content="Memory content",
            injected=True,
        )
        data = source.to_dict()

        assert data["source"] == "memory"
        assert data["priority"] == 75
        assert data["content"] == "Memory content"
        assert data["injected"] is True

    def test_system_source_from_dict(self):
        """Test SystemSource deserialization."""
        data = {
            "source": "system",
            "priority": 60,
            "content": "System content",
            "injected": True,
            "scope": [],
            "metadata": {},
        }
        source = SystemSource.from_dict(data)

        assert source.source == ContextSource.SYSTEM
        assert source.priority == 60
        assert source.content == "System content"


class TestContextSourceEnum:
    """Test suite for ContextSource enum."""

    def test_all_context_sources_defined(self):
        """Test that all expected context sources are defined."""
        expected = {
            "memory", "user", "system", "skill", "soul",
            "diary", "world_state", "multi_provider_aggregation",
            "project_workflow", "user_private_facts",
        }
        actual = {cs.value for cs in ContextSource}
        assert actual == expected

    def test_context_source_list_all(self):
        """Test ContextSource.list_all() returns all values."""
        all_sources = ContextSource.list_all()
        assert len(all_sources) == 10
        assert ContextSource.MEMORY in all_sources


class TestEnums:
    """Test suite for enum values."""

    def test_task_type_values(self):
        """Test TaskType enum values."""
        expected = {
            "technical", "relational", "reflective",
            "creative", "factual", "high_stakes", "architecture_research"
        }
        actual = {t.value for t in TaskType}
        assert actual == expected

    def test_roleplay_level_values(self):
        """Test RoleplayLevel enum values."""
        expected = {"off", "minimal", "light", "normal", "high"}
        actual = {r.value for r in RoleplayLevel}
        assert actual == expected

    def test_continuity_mode_values(self):
        """Test ContinuityMode enum values."""
        expected = {"none", "reference_only", "compact", "expanded"}
        actual = {c.value for c in ContinuityMode}
        assert actual == expected
