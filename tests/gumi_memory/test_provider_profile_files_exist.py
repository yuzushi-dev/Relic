"""Tests verifying provider profile configuration files exist.

These tests verify:
- All required profile YAML files exist
- Profile files are valid YAML
- Profile files contain no forbidden patterns
"""

from pathlib import Path

import pytest

# Get the root of the repository - go up from tests/gumi_memory/test_xxx.py
# tests/gumi_memory -> tests -> repo root
REPO_ROOT = (Path(__file__).parent.parent.parent).resolve()


class TestProviderProfileFilesExist:
    """Tests verifying profile configuration files exist."""

    def test_configs_hermes_profiles_directory_exists(self):
        """Verify configs/hermes/profiles directory exists."""
        profiles_dir = REPO_ROOT / "configs" / "hermes" / "profiles"
        assert profiles_dir.exists(), \
            f"Directory {profiles_dir} does not exist"

    def test_c0_builtin_profile_exists(self):
        """Verify C0 builtin profile YAML exists."""
        profile_path = REPO_ROOT / "configs" / "hermes" / "profiles" / "gumi-c0-builtin.yaml"
        assert profile_path.exists(), \
            f"Profile file {profile_path} does not exist"

    def test_c1_holographic_profile_exists(self):
        """Verify C1 holographic profile YAML exists."""
        profile_path = REPO_ROOT / "configs" / "hermes" / "profiles" / "gumi-c1-holographic.yaml"
        assert profile_path.exists(), \
            f"Profile file {profile_path} does not exist"

    def test_c2_hindsight_tools_profile_exists(self):
        """Verify C2 hindsight-tools profile YAML exists."""
        profile_path = REPO_ROOT / "configs" / "hermes" / "profiles" / "gumi-c2-hindsight-tools.yaml"
        assert profile_path.exists(), \
            f"Profile file {profile_path} does not exist"

    def test_c3_hindsight_context_profile_exists(self):
        """Verify C3 hindsight-context profile YAML exists."""
        profile_path = REPO_ROOT / "configs" / "hermes" / "profiles" / "gumi-c3-hindsight-context.yaml"
        assert profile_path.exists(), \
            f"Profile file {profile_path} does not exist"

    def test_c4_byterover_profile_exists(self):
        """Verify C4 byterover profile YAML exists."""
        profile_path = REPO_ROOT / "configs" / "hermes" / "profiles" / "gumi-c4-byterover.yaml"
        assert profile_path.exists(), \
            f"Profile file {profile_path} does not exist"

    def test_c5_honcho_profile_exists(self):
        """Verify C5 honcho profile YAML exists."""
        profile_path = REPO_ROOT / "configs" / "hermes" / "profiles" / "gumi-c5-honcho.yaml"
        assert profile_path.exists(), \
            f"Profile file {profile_path} does not exist"

    def test_all_six_profiles_exist(self):
        """Verify all six profile files exist."""
        profiles = [
            "gumi-c0-builtin.yaml",
            "gumi-c1-holographic.yaml",
            "gumi-c2-hindsight-tools.yaml",
            "gumi-c3-hindsight-context.yaml",
            "gumi-c4-byterover.yaml",
            "gumi-c5-honcho.yaml",
        ]

        profiles_dir = REPO_ROOT / "configs" / "hermes" / "profiles"

        for profile in profiles:
            profile_path = profiles_dir / profile
            assert profile_path.exists(), \
                f"Required profile {profile} does not exist at {profile_path}"

    def test_profiles_are_valid_yaml(self):
        """Verify all profile files are valid YAML."""
        import yaml

        profiles = [
            "gumi-c0-builtin.yaml",
            "gumi-c1-holographic.yaml",
            "gumi-c2-hindsight-tools.yaml",
            "gumi-c3-hindsight-context.yaml",
            "gumi-c4-byterover.yaml",
            "gumi-c5-honcho.yaml",
        ]

        profiles_dir = REPO_ROOT / "configs" / "hermes" / "profiles"

        for profile in profiles:
            profile_path = profiles_dir / profile
            if profile_path.exists():
                with open(profile_path) as f:
                    try:
                        yaml.safe_load(f)
                    except yaml.YAMLError as e:
                        pytest.fail(f"Profile {profile} is not valid YAML: {e}")

    def test_profiles_contain_no_secrets(self):
        """Verify all profile files contain no secrets or API keys."""
        forbidden_patterns = [
            "API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY",
            "honcho_api_key", "honcho.*api.key", "hindsight_token",
            "hindsight.*token", "byterover_token", "byterover.*token",
            "sk-", "sk1-", "sk2-",
        ]

        profiles = [
            "gumi-c0-builtin.yaml",
            "gumi-c1-holographic.yaml",
            "gumi-c2-hindsight-tools.yaml",
            "gumi-c3-hindsight-context.yaml",
            "gumi-c4-byterover.yaml",
            "gumi-c5-honcho.yaml",
        ]

        profiles_dir = REPO_ROOT / "configs" / "hermes" / "profiles"

        for profile in profiles:
            profile_path = profiles_dir / profile
            if profile_path.exists():
                content = profile_path.read_text()

                for pattern in forbidden_patterns:
                    clean_pattern = pattern.replace(".*", "")
                    assert clean_pattern not in content, \
                        f"Profile {profile} contains forbidden pattern: {pattern}"

    def test_c4_c5_profiles_are_pr19_provider_evaluation(self):
        """Verify ByteRover and Honcho use the PR19 provider-evaluation class."""
        import yaml

        profiles_dir = REPO_ROOT / "configs" / "hermes" / "profiles"
        for profile in ("gumi-c4-byterover.yaml", "gumi-c5-honcho.yaml"):
            profile_path = profiles_dir / profile
            with open(profile_path) as f:
                data = yaml.safe_load(f)

            assert data["integration_class"] == "pr19-provider-evaluation"
            assert data["status"] == "skipped"
            assert data["memory"]["enabled"] is False
            assert "PR20" not in profile_path.read_text()
