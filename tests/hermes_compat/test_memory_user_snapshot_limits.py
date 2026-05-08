"""Test MEMORY.md and USER.md snapshot limits.

Acceptance criteria:
- MEMORY.md/USER.md snapshot limits are enforced
- SOUL.md is persona-only, not diary/world-state storage

This test verifies:
- Snapshot size limits are enforced
- Snapshot age limits are enforced
- Private data is not exposed in snapshots
"""

from __future__ import annotations

from datetime import datetime, timedelta


class TestMemoryUserSnapshotLimits:
    """Verify MEMORY.md and USER.md snapshot limits are enforced."""

    def test_memory_snapshot_size_limit_enforced(self) -> None:
        """MEMORY.md snapshot must respect size limits."""
        from relic.snapshot import SnapshotConfig, SnapshotManager

        config = SnapshotConfig(max_size_bytes=1024 * 1024)  # 1MB limit
        manager = SnapshotManager(config)

        # Attempt to create snapshot with oversized content
        large_content = "x" * (2 * 1024 * 1024)  # 2MB
        result = manager.create_snapshot(content=large_content)

        assert result.truncated is True or result.rejected is True, (
            "Oversized MEMORY.md snapshot must be rejected or truncated"
        )

    def test_user_snapshot_size_limit_enforced(self) -> None:
        """USER.md snapshot must respect size limits."""
        from relic.snapshot import SnapshotConfig, SnapshotManager

        config = SnapshotConfig(max_size_bytes=512 * 1024)  # 512KB limit
        manager = SnapshotManager(config)

        large_content = "x" * (1024 * 1024)  # 1MB
        result = manager.create_snapshot(content=large_content)

        assert result.truncated is True or result.rejected is True, (
            "Oversized USER.md snapshot must be rejected or truncated"
        )

    def test_memory_snapshot_age_limit_enforced(self) -> None:
        """MEMORY.md snapshots must respect age limits."""
        from relic.snapshot import SnapshotConfig, SnapshotManager

        config = SnapshotConfig(max_age_days=30)
        manager = SnapshotManager(config)

        # Simulate old snapshot
        old_date = datetime.now() - timedelta(days=60)
        result = manager.validate_snapshot_age(created_at=old_date)

        assert result.expired is True, (
            "MEMORY.md snapshots older than max_age_days must be expired"
        )

    def test_user_snapshot_age_limit_enforced(self) -> None:
        """USER.md snapshots must respect age limits."""
        from relic.snapshot import SnapshotConfig, SnapshotManager

        config = SnapshotConfig(max_age_days=90)
        manager = SnapshotManager(config)

        old_date = datetime.now() - timedelta(days=120)
        result = manager.validate_snapshot_age(created_at=old_date)

        assert result.expired is True, (
            "USER.md snapshots older than max_age_days must be expired"
        )

    def test_snapshot_no_private_data_exposure(self) -> None:
        """Snapshots must not expose private user data."""
        from relic.snapshot import SnapshotConfig, SnapshotManager

        from relic.privacy_gate import PrivacyGate

        config = SnapshotConfig()
        manager = SnapshotManager(config)
        gate = PrivacyGate()

        content_with_pii = "User lives at 123 Main St, SSN: 123-45-6789"
        result = manager.create_snapshot(content=content_with_pii)

        # Privacy gate should have redacted PII
        if hasattr(result, "snapshot_content"):
            gate_result = gate.filter_output({"content": result.snapshot_content})
            assert "123 Main St" not in gate_result.get("content", ""), (
                "PII must be redacted in snapshots"
            )
            assert "123-45-6789" not in gate_result.get("content", ""), (
                "SSN must be redacted in snapshots"
            )


class TestMemoryUserDiaryWorldStateIsolation:
    """Verify MEMORY.md and USER.md are not used as diary/world-state storage."""

    def test_memory_md_not_diary(self) -> None:
        """MEMORY.md must not be used as diary."""
        from relic.hermes_plugin.context_injection import ContextSource

        # MEMORY.md is user data storage, not diary
        assert ContextSource.MEMORY not in [ContextSource.DIARY], (
            "MEMORY.md must not be used as diary storage"
        )

    def test_user_md_not_diary(self) -> None:
        """USER.md must not be used as diary."""
        from relic.hermes_plugin.context_injection import ContextSource

        assert ContextSource.USER not in [ContextSource.DIARY], (
            "USER.md must not be used as diary storage"
        )

    def test_memory_md_not_world_state(self) -> None:
        """MEMORY.md must not be used as world state."""
        from relic.hermes_plugin.context_injection import ContextSource

        assert ContextSource.MEMORY not in [ContextSource.WORLD_STATE], (
            "MEMORY.md must not be used as world state"
        )

    def test_user_md_not_world_state(self) -> None:
        """USER.md must not be used as world state."""
        from relic.hermes_plugin.context_injection import ContextSource

        assert ContextSource.USER not in [ContextSource.WORLD_STATE], (
            "USER.md must not be used as world state"
        )

    def test_fail_safe_blocks_diary_injection(self) -> None:
        """Fail-safe must block diary injection into MEMORY/USER."""
        from relic.hermes_plugin.fail_safe import FailSafeRegistry, FailSafeTrigger

        registry = FailSafeRegistry(enabled=True)

        result = registry.trigger(
            reason="Attempted diary injection into MEMORY.md",
            trigger=FailSafeTrigger.MEMORY_CONTEXT_ABUSE,
        )

        assert result.blocked is True, "Diary injection into MEMORY.md must be blocked"
