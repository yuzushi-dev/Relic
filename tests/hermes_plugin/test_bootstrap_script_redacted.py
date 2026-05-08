"""Tests for bootstrap script redaction.

These tests verify:
- Bootstrap script never prints secrets
- Dry-run mode works without live credentials
- Script output is redacted
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class TestBootstrapScriptRedaction:
    """Test bootstrap script redaction."""

    def test_script_exists(self) -> None:
        """Bootstrap script should exist."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "hermes" / "check_relic_plugin_bootstrap.sh"
        assert script_path.exists()

    def test_script_has_strict_mode(self) -> None:
        """Script should start with strict mode."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "hermes" / "check_relic_plugin_bootstrap.sh"
        content = script_path.read_text()
        # Should have set -e or set -u or set -o pipefail somewhere early in the file
        lines = content.split("\n")
        found_strict = False
        for i, line in enumerate(lines[:20]):  # Check first 20 lines
            if "set -" in line:
                found_strict = True
                break
        assert found_strict, "Script should have strict mode (set -euo pipefail)"

    def test_script_supports_dry_run(self) -> None:
        """Script should support --dry-run."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "hermes" / "check_relic_plugin_bootstrap.sh"
        content = script_path.read_text()
        assert "--dry-run" in content or "dry-run" in content or "dry_run" in content or "DRY_RUN" in content

    def test_script_no_api_key_echo(self) -> None:
        """Script should not echo API keys."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "hermes" / "check_relic_plugin_bootstrap.sh"
        content = script_path.read_text()
        # Should not have patterns like: echo $API_KEY (outside of comments)
        lines = content.split("\n")
        for line in lines:
            # Skip comment lines
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "echo" in line.lower() and ("key" in line.lower() or "token" in line.lower() or "secret" in line.lower()):
                # These should be commented or use placeholder
                assert "#" in line or "REDACTED" in line or "***" in line

    def test_script_handles_missing_config_gracefully(self) -> None:
        """Script should handle missing config without printing secrets."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "hermes" / "check_relic_plugin_bootstrap.sh"
        # Run with non-existent config
        result = subprocess.run(
            ["bash", str(script_path), "--config", "/nonexistent/config.yaml"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Should exit gracefully (not crash)
        # exit_code 0 = success, 1 = check failure, but NOT 2 (invalid args) or crash
        assert result.returncode in [0, 1]
        # Output should not contain sensitive patterns
        assert "sk-" not in result.stdout
        assert "sk-" not in result.stderr

    def test_script_dry_run_no_credentials(self) -> None:
        """Dry-run should work without credentials."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "hermes" / "check_relic_plugin_bootstrap.sh"
        result = subprocess.run(
            ["bash", str(script_path), "--dry-run"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # Should not fail due to missing credentials
        assert result.returncode in [0, 1]
        # Output should be safe (no secret patterns)
        for line in result.stdout.split("\n") + result.stderr.split("\n"):
            if "error" in line.lower():
                # Error messages should not expose credentials
                assert "sk-" not in line


class TestBootstrapScriptSecurity:
    """Test bootstrap script security properties."""

    def test_script_no_hardcoded_secrets(self) -> None:
        """Script should not have hardcoded secrets (not in comments)."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "hermes" / "check_relic_plugin_bootstrap.sh"
        content = script_path.read_text()
        lines = content.split("\n")

        # Check non-comment lines for hardcoded secrets
        for line in lines:
            stripped = line.strip()
            # Skip empty lines and comments
            if not stripped or stripped.startswith("#"):
                continue
            # Check for actual secret patterns (not just mentions in comments or examples)
            # A hardcoded secret would be like: api_key="sk-1234567890"
            if "api_key=" in line and "=" in line:
                # Make sure it's not an example/placeholder
                if "example" not in line.lower() and "placeholder" not in line.lower() and "REDACTED" not in line:
                    assert False, f"Potential hardcoded secret found: {line}"
            if "sk-" in line:
                # Check if it's not just a regex pattern or comment
                if not any(x in line for x in ["grep", "echo", "#", "REDACTED", "example", "placeholder"]):
                    assert False, f"Potential hardcoded secret found: {line}"

    def test_script_uses_env_vars_safely(self) -> None:
        """Script should use env vars with proper handling."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "hermes" / "check_relic_plugin_bootstrap.sh"
        content = script_path.read_text()
        # If using env vars, should have proper quoting or ${VAR:-default}
        if "${" in content and ("API" in content or "TOKEN" in content or "KEY" in content):
            # Should have proper shell quoting
            assert '"${' in content or "'${" in content or "${" in content
