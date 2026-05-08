"""
Test module: Profile Tool Boundaries
Cron and profile specs

Tests tool permission boundaries for companion, maintainer, and lab profiles.
Must assert acceptance criteria and fail closed on privacy/correction/runtime bypass.
"""

from pathlib import Path

import pytest
import yaml

# Load profile fixtures
PROFILES_DIR = Path(__file__).parent.parent.parent / "profiles"


def load_profile(name: str) -> dict:
    """Load a profile configuration by name."""
    profile_path = PROFILES_DIR / f"{name}.yaml"
    assert profile_path.exists(), f"Profile {name} not found at {profile_path}"
    with open(profile_path) as f:
        return yaml.safe_load(f)


class TestCompanionProfile:
    """Tests for companion profile tool boundaries."""

    @pytest.fixture
    def companion(self) -> dict:
        return load_profile("companion")

    def test_companion_cannot_run_lab_jobs(self, companion: dict) -> None:
        """Acceptance: companion cannot run lab jobs."""
        capabilities = companion.get("capabilities", {})
        lab_jobs = capabilities.get("lab_jobs", {})

        # Lab jobs must be explicitly denied
        assert lab_jobs.get("allowed") is False, (
            "Companion profile MUST deny lab_jobs capability"
        )

    def test_companion_tool_permissions(self, companion: dict) -> None:
        """Verify companion has restricted tool permissions."""
        tools = companion.get("tools", {})
        denied = tools.get("denied", [])

        # Must deny dangerous tools
        assert "provider.call" in denied, "provider.call must be denied"
        assert "tool.execute" in denied, "tool.execute must be denied"
        assert "memory.update" in denied, "memory.update must be denied"
        assert "memory.delete" in denied, "memory.delete must be denied"

    def test_companion_memory_restrictions(self, companion: dict) -> None:
        """Verify companion memory access is read/append only."""
        capabilities = companion.get("capabilities", {})
        memory = capabilities.get("memory", {})

        assert memory.get("read") is True
        assert memory.get("write") is True
        assert memory.get("modify") is False
        assert memory.get("delete") is False

    def test_companion_chat_enabled(self, companion: dict) -> None:
        """Verify companion has chat enabled."""
        capabilities = companion.get("capabilities", {})
        chat = capabilities.get("chat", {})

        assert chat.get("enabled") is True, "Companion must have chat enabled"

    def test_companion_privacy_settings(self, companion: dict) -> None:
        """Verify companion has privacy output filter."""
        privacy = companion.get("privacy", {})

        assert privacy.get("output_filter") is True
        assert privacy.get("pii_detection") is True
        assert privacy.get("auto_redact") is True


class TestRelicMaintainerProfile:
    """Tests for relic-maintainer profile tool boundaries."""

    @pytest.fixture
    def maintainer(self) -> dict:
        return load_profile("relic-maintainer")

    def test_maintainer_cannot_chat_normally(self, maintainer: dict) -> None:
        """Acceptance: maintainer cannot chat normally."""
        capabilities = maintainer.get("capabilities", {})
        chat = capabilities.get("chat", {})

        # Chat must be explicitly disabled
        assert chat.get("enabled") is False, (
            "Maintainer profile MUST deny chat capability"
        )

    def test_maintainer_has_maintenance_access(self, maintainer: dict) -> None:
        """Verify maintainer has full maintenance access."""
        capabilities = maintainer.get("capabilities", {})
        maintenance = capabilities.get("maintenance", {})

        assert maintenance.get("enabled") is True
        assert maintenance.get("full_access") is True

    def test_maintainer_tool_permissions(self, maintainer: dict) -> None:
        """Verify maintainer has elevated but restricted tool permissions."""
        tools = maintainer.get("tools", {})
        denied = tools.get("denied", [])

        # Must deny dangerous tools
        assert "provider.call" in denied, "provider.call must be denied for maintainer"
        assert "tool.execute" in denied, "tool.execute must be denied for maintainer"

    def test_maintainer_memory_full_access(self, maintainer: dict) -> None:
        """Verify maintainer has full memory access."""
        capabilities = maintainer.get("capabilities", {})
        memory = capabilities.get("memory", {})

        assert memory.get("read") is True
        assert memory.get("write") is True
        assert memory.get("modify") is True
        assert memory.get("delete") is True

    def test_maintainer_audit_verbose(self, maintainer: dict) -> None:
        """Verify maintainer has verbose audit logging."""
        audit = maintainer.get("audit", {})

        assert audit.get("enabled") is True
        assert audit.get("level") == "verbose"


class TestRelicLabProfile:
    """Tests for relic-lab profile tool boundaries."""

    @pytest.fixture
    def lab(self) -> dict:
        return load_profile("relic-lab")

    def test_lab_has_lab_jobs_enabled(self, lab: dict) -> None:
        """Verify lab profile has lab jobs enabled."""
        capabilities = lab.get("capabilities", {})
        lab_jobs = capabilities.get("lab_jobs", {})

        assert lab_jobs.get("enabled") is True
        assert "evaluation" in lab_jobs.get("job_types", [])
        assert "dataset-generation" in lab_jobs.get("job_types", [])
        assert "replication" in lab_jobs.get("job_types", [])

    def test_lab_cannot_publish_runtime_artifact_without_promotion_gate(
        self, lab: dict
    ) -> None:
        """Acceptance: lab cannot publish runtime artifact without promotion gate."""
        promotion_gate = lab.get("promotion_gate", {})

        # Promotion gate must be enabled
        assert promotion_gate.get("enabled") is True, (
            "Lab profile MUST have promotion gate enabled"
        )

        # Must require approval for runtime artifacts
        artifact_types = promotion_gate.get("artifact_types", {})
        runtime_artifact = artifact_types.get("runtime_artifact", {})
        assert runtime_artifact.get("requires_promotion") is True
        assert runtime_artifact.get("promotion_approval_required") is True

        # Must block direct publish
        blocked = promotion_gate.get("blocked_actions", [])
        assert "direct_publish" in blocked, "direct_publish must be blocked"
        assert "runtime_deployment" in blocked, "runtime_deployment must be blocked"

    def test_lab_tool_permissions(self, lab: dict) -> None:
        """Verify lab has evaluation-appropriate tool permissions."""
        tools = lab.get("tools", {})
        denied = tools.get("denied", [])

        # Must deny dangerous tools
        assert "tool.execute" in denied, "tool.execute must be denied"
        assert "memory.delete" in denied, "memory.delete must be denied"

    def test_lab_memory_restrictions(self, lab: dict) -> None:
        """Verify lab memory access restrictions."""
        capabilities = lab.get("capabilities", {})
        memory = capabilities.get("memory", {})

        # Research data retention - no delete
        assert memory.get("read") is True
        assert memory.get("write") is True
        assert memory.get("modify") is True
        assert memory.get("delete") is False

    def test_lab_promotion_gate_requires_approval(self, lab: dict) -> None:
        """Verify promotion gate requires security review approval."""
        promotion_gate = lab.get("promotion_gate", {})
        approvals = promotion_gate.get("required_approvals", [])

        assert "security-review" in approvals, (
            "Promotion gate must require security-review approval"
        )


class TestToolBoundaryIsolation:
    """Integration tests for tool boundary isolation between profiles."""

    def test_companion_vs_lab_boundary(self) -> None:
        """Verify companion cannot access lab capabilities."""
        companion = load_profile("companion")
        lab = load_profile("relic-lab")

        # Companion denies what lab allows
        companion_lab_jobs = companion.get("capabilities", {}).get("lab_jobs", {})
        lab_lab_jobs = lab.get("capabilities", {}).get("lab_jobs", {})

        assert companion_lab_jobs.get("allowed") is False
        assert lab_lab_jobs.get("enabled") is True

    def test_maintainer_vs_companion_boundary(self) -> None:
        """Verify maintainer cannot chat like companion."""
        maintainer = load_profile("relic-maintainer")
        companion = load_profile("companion")

        # Maintainer denies chat, companion allows it
        maintainer_chat = maintainer.get("capabilities", {}).get("chat", {})
        companion_chat = companion.get("capabilities", {}).get("chat", {})

        assert maintainer_chat.get("enabled") is False
        assert companion_chat.get("enabled") is True

    def test_lab_promotion_gate_enforced(self) -> None:
        """Verify lab promotion gate is properly configured."""
        lab = load_profile("relic-lab")
        promotion_gate = lab.get("promotion_gate", {})

        # Gate must exist and be enabled
        assert "promotion_gate" in lab
        assert promotion_gate.get("enabled") is True

        # Runtime artifacts must require promotion
        artifact_types = promotion_gate.get("artifact_types", {})
        assert "runtime_artifact" in artifact_types
        assert artifact_types["runtime_artifact"]["requires_promotion"] is True
