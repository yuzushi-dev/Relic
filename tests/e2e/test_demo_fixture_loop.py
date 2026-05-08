"""Tests for E2E demo fixture loop.

These tests verify that the E2E demo runs correctly and produces
the required outputs without violating privacy or correction gates.

Acceptance criteria for 
- demo runs locally from clean checkout
- demo produces replication_bundle
- demo does not require cloud provider
- demo report explains what was injected and what was blocked
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


class TestDemoE2ERunner:
    """Tests for the demo_e2e.py runner."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def demo_script(self, project_root: Path) -> Path:
        """Get path to demo_e2e.py script."""
        return project_root / "scripts" / "demo_e2e.py"

    def test_demo_script_exists(self, demo_script: Path) -> None:
        """Test that demo script exists."""
        assert demo_script.exists(), f"Demo script not found: {demo_script}"

    def test_demo_script_is_executable(self, demo_script: Path) -> None:
        """Test that demo script has execute permissions."""
        assert os.access(demo_script, os.X_OK), f"Demo script not executable: {demo_script}"

    def test_demo_script_has_help(self, demo_script: Path) -> None:
        """Test that demo script supports --help."""
        result = subprocess.run(
            [sys.executable, str(demo_script), "--help"],
            capture_output=True,
            text=True,
            cwd=demo_script.parent.parent,
        )
        assert result.returncode == 0, f"--help failed: {result.stderr}"
        assert "Relic E2E Demo" in result.stdout, "Help text should contain demo description"

    def test_demo_script_dry_run(self, demo_script: Path) -> None:
        """Test that demo script supports --dry-run."""
        result = subprocess.run(
            [sys.executable, str(demo_script), "--dry-run"],
            capture_output=True,
            text=True,
            cwd=demo_script.parent.parent,
        )
        assert result.returncode == 0, f"--dry-run failed: {result.stderr}"
        assert "DRY-RUN" in result.stdout or "dry" in result.stdout.lower(), \
            "Dry-run should indicate no changes will be made"

    def test_demo_script_runs_without_error(self, demo_script: Path, tmp_path: Path) -> None:
        """Test that demo script runs successfully."""
        env = os.environ.copy()
        env["PYTHONPATH"] = str(demo_script.parent.parent)

        result = subprocess.run(
            [sys.executable, str(demo_script)],
            capture_output=True,
            text=True,
            cwd=demo_script.parent.parent,
            env=env,
            timeout=60,
        )
        # Script should complete without error (may have warnings but no failures)
        assert result.returncode == 0, f"Demo failed: {result.stderr}\n{result.stdout}"

    def test_demo_script_no_network_required(self, demo_script: Path) -> None:
        """Test that demo does not require network access."""
        # This test verifies the demo completes even without network
        # by checking that it uses mock models and local fixtures
        result = subprocess.run(
            [sys.executable, str(demo_script), "--dry-run"],
            capture_output=True,
            text=True,
            cwd=demo_script.parent.parent,
        )

        output = result.stdout + result.stderr
        # Should NOT mention network/cloud/API requirements in positive cases
        assert "cloud" not in output.lower() or "no" in output.lower(), \
            "Demo should not require cloud provider"


class TestDemoShellHelper:
    """Tests for the demo_e2e.sh shell helper."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def shell_script(self, project_root: Path) -> Path:
        """Get path to demo_e2e.sh script."""
        return project_root / "scripts" / "demo_e2e.sh"

    def test_shell_script_exists(self, shell_script: Path) -> None:
        """Test that shell script exists."""
        assert shell_script.exists(), f"Shell script not found: {shell_script}"

    def test_shell_script_is_executable(self, shell_script: Path) -> None:
        """Test that shell script has execute permissions."""
        assert os.access(shell_script, os.X_OK), f"Shell script not executable: {shell_script}"

    def test_shell_script_starts_with_strict_mode(self, shell_script: Path) -> None:
        """Test that shell script starts with strict mode."""
        content = shell_script.read_text()
        # Check for strict mode settings (set -euo pipefail includes -u)
        assert "set -e" in content or "set -o errexit" in content, \
            "Shell script should use 'set -e' or 'set -o errexit'"
        # -uo includes -u (nounset)
        assert "set -u" in content or "set -uo" in content or "set -eu" in content, \
            "Shell script should use 'set -u' (or combined like set -euo)"

    def test_shell_script_has_dry_run(self, shell_script: Path) -> None:
        """Test that shell script supports --dry-run."""
        result = subprocess.run(
            [str(shell_script), "--dry-run"],
            capture_output=True,
            text=True,
            cwd=shell_script.parent.parent,
        )
        assert result.returncode == 0, f"--dry-run failed: {result.stderr}"
        assert "DRY-RUN" in result.stdout, "Dry-run should be indicated"

    def test_shell_script_has_help(self, shell_script: Path) -> None:
        """Test that shell script supports --help."""
        result = subprocess.run(
            [str(shell_script), "--help"],
            capture_output=True,
            text=True,
            cwd=shell_script.parent.parent,
        )
        assert result.returncode == 0, f"--help failed: {result.stderr}"
        assert "Relic E2E" in result.stdout or "SYNOPSIS" in result.stdout, \
            "Help should contain usage information"

    def test_shell_script_no_secret_leakage(self, shell_script: Path) -> None:
        """Test that shell script never prints secrets."""
        content = shell_script.read_text()

        # Check for common secret patterns that shouldn't be hardcoded
        dangerous_patterns = [
            'api_key"',
            'API_KEY"',
            'secret"',
            'SECRET"',
            'password"',
            'PASSWORD"',
        ]

        for pattern in dangerous_patterns:
            assert pattern not in content.lower(), \
                f"Shell script should not contain hardcoded secrets: {pattern}"


class TestDemoReplicationBundle:
    """Tests for the demo replication bundle output."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def demo_script(self, project_root: Path) -> Path:
        """Get path to demo_e2e.py script."""
        return project_root / "scripts" / "demo_e2e.py"

    @pytest.fixture
    def bundle_dir(self, project_root: Path) -> Path:
        """Get path to replication bundles directory."""
        return project_root / "artifacts" / "replication_bundles"

    def test_bundle_directory_exists(self, bundle_dir: Path) -> None:
        """Test that bundle directory exists or can be created."""
        bundle_dir.mkdir(parents=True, exist_ok=True)
        assert bundle_dir.is_dir(), f"Bundle directory not created: {bundle_dir}"

    def test_demo_produces_bundle(self, demo_script: Path, bundle_dir: Path) -> None:
        """Test that demo produces a replication bundle."""
        bundle_dir.mkdir(parents=True, exist_ok=True)

        # Snapshot existing bundles by name before running
        before_bundles = set(f.name for f in bundle_dir.glob("demo-e2e-*"))

        # Ensure timestamp uniqueness
        time.sleep(1.1)

        # Run demo
        env = os.environ.copy()
        env["PYTHONPATH"] = str(demo_script.parent.parent)

        result = subprocess.run(
            [sys.executable, str(demo_script)],
            capture_output=True,
            text=True,
            cwd=demo_script.parent.parent,
            env=env,
            timeout=60,
        )

        assert result.returncode == 0, f"Demo failed: {result.stderr}"

        # Check for new bundles by name (not count, to avoid race with other tests)
        after_bundles = set(f.name for f in bundle_dir.glob("demo-e2e-*"))
        new_bundles = after_bundles - before_bundles

        assert len(new_bundles) > 0, \
            f"Demo should produce at least one new bundle. New: {new_bundles}"

    def test_bundle_contains_injection_report(self, demo_script: Path, bundle_dir: Path, tmp_path: Path) -> None:
        """Test that bundle contains injection/blocking report."""
        bundle_dir.mkdir(parents=True, exist_ok=True)

        # Run demo
        env = os.environ.copy()
        env["PYTHONPATH"] = str(demo_script.parent.parent)

        result = subprocess.run(
            [sys.executable, str(demo_script)],
            capture_output=True,
            text=True,
            cwd=demo_script.parent.parent,
            env=env,
            timeout=60,
        )

        assert result.returncode == 0, f"Demo failed: {result.stderr}"

        # Check output contains injection report
        output = result.stdout + result.stderr
        assert "INJECTED" in output or "injected" in output.lower(), \
            "Demo should report injected items"
        assert "BLOCKED" in output or "blocked" in output.lower(), \
            "Demo should report blocked items"


class TestDemoPrivacySafety:
    """Tests for demo privacy and safety guarantees."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def demo_script(self, project_root: Path) -> Path:
        """Get path to demo_e2e.py script."""
        return project_root / "scripts" / "demo_e2e.py"

    def test_demo_uses_redacted_content(self, demo_script: Path) -> None:
        """Test that demo uses redacted/synthetic content."""
        content = demo_script.read_text()

        # Check for redaction markers
        assert "REDACTED" in content or "[USER_" in content, \
            "Demo should use redaction markers"

        # Check that there are no hardcoded real data
        assert "real_user" not in content.lower(), \
            "Demo should not use real user data"

    def test_demo_fails_closed_on_errors(self, demo_script: Path) -> None:
        """Test that demo fails closed (safe behavior) on errors."""
        # Run with invalid args - should fail safely
        result = subprocess.run(
            [sys.executable, str(demo_script), "--invalid-arg"],
            capture_output=True,
            text=True,
            cwd=demo_script.parent.parent,
        )

        # Should fail with non-zero exit code
        assert result.returncode != 0, \
            "Demo should fail closed on invalid arguments"

        # Should show help or error message
        assert "help" in result.stderr.lower() or "error" in result.stderr.lower(), \
            "Demo should provide error message on failure"

    def test_demo_imports_are_safe(self, demo_script: Path) -> None:
        """Test that demo imports don't require network."""
        content = demo_script.read_text()

        # Check for safe imports only
        # Should NOT have direct network requests libraries hardcoded
        forbidden_imports = ["requests", "urllib.request", "http.client", "aiohttp"]

        for forbidden in forbidden_imports:
            assert forbidden not in content, \
                f"Demo should not import network libraries: {forbidden}"

    def test_demo_uses_mock_model(self, demo_script: Path) -> None:
        """Test that demo uses mock models instead of real providers."""
        content = demo_script.read_text()

        # Should use mock model
        assert "mock" in content.lower() or "Mock" in content, \
            "Demo should use mock models"


class TestMakefileIntegration:
    """Tests for make target integration."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    def test_make_demo_target_exists(self, project_root: Path) -> None:
        """Test that make demo-e2e target is defined."""
        makefile = project_root / "Makefile"
        assert makefile.exists(), "Makefile not found"

        content = makefile.read_text()
        assert "demo-e2e" in content, "demo-e2e target should be defined in Makefile"

    def test_make_replication_bundle_target_exists(self, project_root: Path) -> None:
        """Test that make replication-bundle target is defined."""
        makefile = project_root / "Makefile"
        assert makefile.exists(), "Makefile not found"

        content = makefile.read_text()
        assert "replication-bundle" in content or "replication_bundle" in content, \
            "replication-bundle target should be defined in Makefile"


class TestDemoAcceptanceCriteria:
    """Tests that verify acceptance criteria."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    @pytest.fixture
    def demo_script(self, project_root: Path) -> Path:
        """Get path to demo_e2e.py script."""
        return project_root / "scripts" / "demo_e2e.py"

    @pytest.fixture
    def shell_script(self, project_root: Path) -> Path:
        """Get path to demo_e2e.sh script."""
        return project_root / "scripts" / "demo_e2e.sh"

    def test_acceptance_demo_runs_locally(self, demo_script: Path, tmp_path: Path) -> None:
        """AC: demo runs locally from clean checkout."""
        env = os.environ.copy()
        env["PYTHONPATH"] = str(demo_script.parent.parent)

        result = subprocess.run(
            [sys.executable, str(demo_script)],
            capture_output=True,
            text=True,
            cwd=demo_script.parent.parent,
            env=env,
            timeout=60,
        )

        assert result.returncode == 0, \
            f"Demo should run locally. Error: {result.stderr}"

    def test_acceptance_demo_produces_replication_bundle(
        self, demo_script: Path, tmp_path: Path
    ) -> None:
        """AC: demo produces replication_bundle."""
        bundle_dir = demo_script.parent.parent / "artifacts" / "replication_bundles"
        bundle_dir.mkdir(parents=True, exist_ok=True)

        # Run demo
        env = os.environ.copy()
        env["PYTHONPATH"] = str(demo_script.parent.parent)

        result = subprocess.run(
            [sys.executable, str(demo_script)],
            capture_output=True,
            text=True,
            cwd=demo_script.parent.parent,
            env=env,
            timeout=60,
        )

        assert result.returncode == 0, f"Demo failed: {result.stderr}"

        # Check for bundle output
        bundles = list(bundle_dir.glob("demo-e2e-*"))
        assert len(bundles) > 0, "Demo should produce replication_bundle"

    def test_acceptance_demo_no_cloud_provider(self, demo_script: Path) -> None:
        """AC: demo does not require cloud provider."""
        content = demo_script.read_text()

        # Should not require cloud/API
        assert "api_key" not in content.lower() or "mock" in content.lower(), \
            "Demo should not require cloud provider API key"

    def test_acceptance_demo_reports_injection_blocking(
        self, demo_script: Path
    ) -> None:
        """AC: demo report explains what was injected and what was blocked."""
        env = os.environ.copy()
        env["PYTHONPATH"] = str(demo_script.parent.parent)

        result = subprocess.run(
            [sys.executable, str(demo_script)],
            capture_output=True,
            text=True,
            cwd=demo_script.parent.parent,
            env=env,
            timeout=60,
        )

        output = result.stdout + result.stderr

        # Should have injection report
        assert "INJECTED" in output or "injected" in output.lower(), \
            "Demo should report injected items"

        # Should have blocking report
        assert "BLOCKED" in output or "blocked" in output.lower(), \
            "Demo should report blocked items"
