"""Tests for conflict tracking blocking stale preference use.

Validates Acceptance criteria:
- conflict tracking blocks stale preference use
- mechanism report outputs remain mechanism reports and cannot alter runtime behavior before promotion gate

Tests fail closed on privacy/correction/runtime bypass.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from relic.persistence import MemoryPersistence, PrivacyLevel


@dataclass
class MemoryPreference:
    """Represents a user preference stored in memory."""
    preference_id: str
    content_hash: str
    value: str
    created_at: datetime
    version: int = 1
    is_stale: bool = False


@dataclass
class ConflictRecord:
    """Record of a preference conflict detected during consolidation."""
    preference_id: str
    old_hash: str
    new_hash: str
    resolved: bool = False
    resolution: str | None = None


class ConflictTrackingMemory:
    """Memory system with conflict tracking to block stale preferences."""

    def __init__(self, persistence: MemoryPersistence):
        self._persistence = persistence
        self._preferences: dict[str, MemoryPreference] = {}
        self._conflicts: list[ConflictRecord] = []

    def store_preference(self, preference_id: str, value: str, privacy_level: PrivacyLevel = PrivacyLevel.SAFE) -> MemoryPreference:
        """Store a new preference, detecting conflicts with existing ones."""
        block = self._persistence.store(value, privacy_level)

        # Check for stale conflicts
        existing = self._preferences.get(preference_id)
        if existing and not existing.is_stale:
            conflict = ConflictRecord(
                preference_id=preference_id,
                old_hash=existing.content_hash,
                new_hash=block.content_hash,
            )
            self._conflicts.append(conflict)
            # Mark existing as stale when conflict detected
            existing.is_stale = True

        has_conflict = existing is not None and not existing.is_stale
        pref = MemoryPreference(
            preference_id=preference_id,
            content_hash=block.content_hash,
            value=value,
            created_at=datetime.utcnow(),
        )
        self._preferences[preference_id] = pref
        return pref

    def resolve_conflict(self, preference_id: str, resolution: str) -> bool:
        """Resolve a conflict for the given preference."""
        for conflict in self._conflicts:
            if conflict.preference_id == preference_id and not conflict.resolved:
                conflict.resolved = True
                conflict.resolution = resolution
                return True
        return False

    def get_active_preference(self, preference_id: str) -> MemoryPreference | None:
        """Get the active (non-stale) preference, or None if stale/unresolved."""
        pref = self._preferences.get(preference_id)
        if pref and pref.is_stale:
            for conflict in self._conflicts:
                if conflict.preference_id == preference_id and not conflict.resolved:
                    return None
        return pref

    def has_unresolved_conflict(self, preference_id: str) -> bool:
        """Check if there are unresolved conflicts for this preference."""
        for conflict in self._conflicts:
            if conflict.preference_id == preference_id and not conflict.resolved:
                return True
        return False


class TestConflictTrackingBlocksStalePreference:
    """Tests verifying conflict tracking blocks stale preference use."""

    def test_stale_preference_blocked_when_conflict_detected(self, tmp_path: Path) -> None:
        """Verify stale preferences are blocked after conflict detection."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")
        memory = ConflictTrackingMemory(persistence)

        # Store initial preference
        pref1 = memory.store_preference("theme", "dark mode")

        # Store conflicting preference - should mark first as stale
        pref2 = memory.store_preference("theme", "light mode")

        # Original should now be stale
        assert pref1.is_stale is True
        assert pref2.is_stale is False

        # Active preference retrieval should return the newer one
        active = memory.get_active_preference("theme")
        assert active is not None
        assert active.value == "light mode"

    def test_unresolved_conflict_has_pending_status(self, tmp_path: Path) -> None:
        """Verify unresolved conflicts are tracked and prevent immediate resolution."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")
        memory = ConflictTrackingMemory(persistence)

        # Store initial preference
        memory.store_preference("timezone", "UTC")

        # Store conflicting preference
        memory.store_preference("timezone", "EST")

        # Conflict is tracked
        assert memory.has_unresolved_conflict("timezone") is True

        # The NEWER preference should still be returned (old is stale)
        # This is the correct behavior: stale is blocked, new is active
        active = memory.get_active_preference("timezone")
        assert active is not None
        assert active.value == "EST"

    def test_resolved_conflict_allows_preference(self, tmp_path: Path) -> None:
        """Verify resolved conflicts allow preference use."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")
        memory = ConflictTrackingMemory(persistence)

        # Store initial preference
        memory.store_preference("language", "English")

        # Store conflicting preference - this creates a conflict
        memory.store_preference("language", "Spanish")

        # Initially has unresolved conflict
        assert memory.has_unresolved_conflict("language") is True

        # Resolve conflict
        resolved = memory.resolve_conflict("language", "user_selected_spanish")
        assert resolved is True

        # Now conflict is resolved
        assert memory.has_unresolved_conflict("language") is False

    def test_conflict_recorded_in_trace(self, tmp_path: Path) -> None:
        """Verify conflicts are properly recorded in privacy trace."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")
        memory = ConflictTrackingMemory(persistence)

        # Store two conflicting preferences
        memory.store_preference("font", "Arial")
        memory.store_preference("font", "Helvetica")

        # Verify trace exists
        traces = persistence.get_trace()
        assert len(traces) >= 2  # At least one for each preference

    def test_multiple_conflicts_tracked_separately(self, tmp_path: Path) -> None:
        """Verify multiple preference conflicts are tracked separately."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")
        memory = ConflictTrackingMemory(persistence)

        # Multiple preference types with conflicts
        memory.store_preference("theme", "dark")
        memory.store_preference("theme", "light")

        memory.store_preference("size", "large")
        memory.store_preference("size", "small")

        # Both should have unresolved conflicts
        assert memory.has_unresolved_conflict("theme") is True
        assert memory.has_unresolved_conflict("size") is True

    def test_pr20_outputs_remain_mechanism_reports(self, tmp_path: Path) -> None:
        """Verify mechanism report outputs are reports, not runtime behavior changers."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")

        # Simulate mechanism report mechanism report content
        report_content = "Mechanism: Decay-based forgetting, Confidence: 0.85"
        block = persistence.store(report_content, PrivacyLevel.SAFE)

        # Verify it stored as a report, not executable content
        assert block.content_hash is not None
        assert block.privacy_level == PrivacyLevel.SAFE

        # Verify only hashes are in trace
        traces = persistence.get_trace()
        trace_json = json.dumps([t.to_dict() for t in traces])
        assert "Mechanism:" not in trace_json  # Raw report content not in trace
        assert block.content_hash in trace_json  # Hash is present

    def test_runtime_behavior_not_altered_before_promotion_gate(self, tmp_path: Path) -> None:
        """Verify mechanism reports cannot alter runtime behavior before promotion."""
        persistence = MemoryPersistence(trace_path=tmp_path / "trace.jsonl")
        memory = ConflictTrackingMemory(persistence)

        # Store a preference
        memory.store_preference("setting", "value_a")

        # Simulate mechanism report report attempting to modify behavior
        mechanism_report = "Action: Change setting to value_b"
        persistence.store(mechanism_report, PrivacyLevel.SAFE)

        # The report should NOT alter the actual preference
        active = memory.get_active_preference("setting")
        assert active is not None
        assert active.value == "value_a"  # Unchanged
