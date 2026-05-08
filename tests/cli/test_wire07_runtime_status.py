"""Tests for WIRE07 runtime status and doctor commands."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure the relic package is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestRuntimeDoctorReportsMissingSessionKey:
    """Test that runtime doctor reports missing session key."""

    def test_runtime_doctor_reports_missing_session_key(self, tmp_path):
        """Doctor should report an issue when active subjects are missing session key hash."""
        from relic.cli import _runtime_doctor
        from relic.profile.registry import SubjectProfile

        # Create mock subjects directory
        mock_relic_home = tmp_path / "relic"
        mock_relic_home.mkdir()
        subjects_dir = mock_relic_home / "subjects"
        subjects_dir.mkdir()

        # Create a mock subject with active status but no session key hash
        subject_id = "test_subject_123"
        subject_dir = subjects_dir / subject_id
        subject_dir.mkdir()

        # Write subject_profile.json with active status
        profile_data = {
            "subject_id": subject_id,
            "experiment_id": "exp_001",
            "status": "active",
            "hermes_profile_name": f"gumi-{subject_id}",
            "hermes_home": str(subject_dir / ".hermes"),
            "relic_subject_home": str(subject_dir),
            "profile_version": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        (subject_dir / "subject_profile.json").write_text(json.dumps(profile_data))

        # Ensure no session key hash file exists
        assert not (subject_dir / ".session_key_hash").exists()

        # Create a mock ProfileRegistry that returns our test subject
        # Note: mock_profile.relic_subject_home must be a real Path for .exists() to work
        mock_profile = SubjectProfile(
            subject_id=subject_id,
            experiment_id="exp_001",
            status="active",
            hermes_profile_name=f"gumi-{subject_id}",
            hermes_home=subject_dir / ".hermes",
            relic_subject_home=subject_dir,  # Real Path, not mock
            profile_version=1,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )

        with patch("relic.cli.ProfileRegistry") as MockRegistry:
            mock_registry = MagicMock()
            mock_registry.relic_home = mock_relic_home
            mock_registry.list_subjects.return_value = [mock_profile]
            MockRegistry.return_value = mock_registry

            import io
            from contextlib import redirect_stdout, redirect_stderr

            output = io.StringIO()
            errors = io.StringIO()

            with redirect_stdout(output), redirect_stderr(errors):
                result = _runtime_doctor()

        # Doctor should return non-zero when there are issues
        assert result == 1, "Doctor should return non-zero when issues found"

        output_text = output.getvalue()
        errors_text = errors.getvalue()

        # Should mention session key is missing
        combined = output_text + errors_text
        assert "session" in combined.lower() or "missing" in combined.lower(), \
            f"Output should mention session key issue: {combined}"


class TestRuntimeDoctorReportsMissingAllowlistEnforcement:
    """Test that runtime doctor reports missing allowlist enforcement."""

    def test_runtime_doctor_reports_missing_allowlist_enforcement(self):
        """Doctor should report when Hermes allowlist enforcement is not supported."""
        from relic.cli import _runtime_doctor

        # Mock features to show allowlist not supported
        mock_features = {
            "no_agent_cron": False,
            "transform_llm_output": False,
            "session_key_support": False,
            "allowlist_support": False,  # Not supported
        }

        with patch("relic.hermes_runtime.check_hermes_feature_support", return_value=mock_features):
            with patch("relic.hermes_runtime.get_runtime_config", return_value={"initialized": True}):
                with patch("relic.hermes_runtime.init_runtime_config", return_value={"initialized": True}):
                    with patch("relic.cli.shutil.which", return_value="/usr/bin/hermes"):
                        with patch("relic.cli.subprocess.run") as mock_run:
                            mock_run.return_value = MagicMock(returncode=0, stdout="hermes version 1.0", stderr="")

                            import io
                            from contextlib import redirect_stdout, redirect_stderr

                            output = io.StringIO()
                            errors = io.StringIO()

                            with redirect_stdout(output), redirect_stderr(errors):
                                result = _runtime_doctor()

        combined = output.getvalue() + errors.getvalue()

        # Should mention allowlist issue
        assert "allowlist" in combined.lower(), \
            f"Output should mention allowlist issue: {combined}"


class TestSubjectShowHidesRawSessionKey:
    """Test that subject show never exposes raw session key."""

    def test_subject_show_hides_raw_session_key(self, tmp_path):
        """Subject show should display 'yes'/'no' for session key presence, never the hash itself."""
        from relic.cli import _subject_show

        # Create mock registry with a subject
        subject_id = "test_subject_456"
        subject_dir = tmp_path / "subjects" / subject_id
        subject_dir.mkdir(parents=True)

        # Write subject_profile.json
        profile_data = {
            "subject_id": subject_id,
            "experiment_id": "exp_002",
            "status": "active",
            "hermes_profile_name": f"gumi-{subject_id}",
            "hermes_home": str(subject_dir / ".hermes"),
            "relic_subject_home": str(subject_dir),
            "profile_version": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        (subject_dir / "subject_profile.json").write_text(json.dumps(profile_data))

        # Write a fake session key hash (to simulate one existing)
        fake_hash = "abcd1234efgh5678ijkl9012mnop3456qrst7890uvwx4567yzab8901"
        (subject_dir / ".session_key_hash").write_text(fake_hash)

        # Mock the registry - patch where it's used (relic.cli module)
        mock_profile = MagicMock()
        mock_profile.subject_id = subject_id
        mock_profile.status = "active"
        mock_profile.hermes_profile_name = f"gumi-{subject_id}"
        mock_profile.relic_subject_home = subject_dir

        with patch("relic.cli.ProfileRegistry") as MockRegistry:
            mock_registry = MagicMock()
            mock_registry.get_subject.return_value = mock_profile
            mock_registry._delivery_policy_path.return_value = subject_dir / "delivery_policy.json"
            MockRegistry.return_value = mock_registry

            import io
            from contextlib import redirect_stdout

            output = io.StringIO()

            with redirect_stdout(output):
                result = _subject_show(subject_id)

        output_text = output.getvalue()

        # Should show session_key_hash with yes/no
        assert "session_key_hash:" in output_text, f"Output should contain session_key_hash field: {output_text}"

        # Should NOT contain the actual hash
        assert fake_hash not in output_text, \
            f"Output should NOT contain raw session key hash: {output_text}"

        # Should show "yes" to indicate session key is present
        assert "yes" in output_text, f"Output should show 'yes' for session_key_hash: {output_text}"

    def test_subject_show_hides_raw_session_key_when_missing(self, tmp_path):
        """Subject show should display 'no' when session key hash is missing."""
        from relic.cli import _subject_show

        subject_id = "test_subject_no_key"
        subject_dir = tmp_path / "subjects" / subject_id
        subject_dir.mkdir(parents=True)

        # Write subject_profile.json without session key hash
        profile_data = {
            "subject_id": subject_id,
            "experiment_id": "exp_003",
            "status": "active",
            "hermes_profile_name": f"gumi-{subject_id}",
            "hermes_home": str(subject_dir / ".hermes"),
            "relic_subject_home": str(subject_dir),
            "profile_version": 1,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        (subject_dir / "subject_profile.json").write_text(json.dumps(profile_data))

        # Ensure no session key hash file exists
        assert not (subject_dir / ".session_key_hash").exists()

        mock_profile = MagicMock()
        mock_profile.subject_id = subject_id
        mock_profile.status = "active"
        mock_profile.hermes_profile_name = f"gumi-{subject_id}"
        mock_profile.relic_subject_home = subject_dir

        with patch("relic.cli.ProfileRegistry") as MockRegistry:
            mock_registry = MagicMock()
            mock_registry.get_subject.return_value = mock_profile
            mock_registry._delivery_policy_path.return_value = subject_dir / "delivery_policy.json"
            MockRegistry.return_value = mock_registry

            import io
            from contextlib import redirect_stdout

            output = io.StringIO()

            with redirect_stdout(output):
                result = _subject_show(subject_id)

        output_text = output.getvalue()

        # Should show "no" for session key
        assert "no" in output_text, f"Output should show 'no' when session key is missing: {output_text}"


class TestRuntimeStatusCommand:
    """Test the runtime status command output."""

    def test_runtime_status_shows_features(self):
        """Runtime status should show Hermes version and feature support."""
        from relic.cli import _runtime_status

        mock_features = {
            "no_agent_cron": True,
            "transform_llm_output": True,
            "session_key_support": True,
            "allowlist_support": True,
        }

        with patch("relic.hermes_runtime.check_hermes_feature_support", return_value=mock_features):
            with patch("relic.hermes_runtime.get_runtime_config", return_value={"initialized": True}):
                with patch("relic.hermes_runtime.init_runtime_config", return_value={"initialized": True}):
                    with patch("relic.cli.shutil.which", return_value="/usr/bin/hermes"):
                        with patch("relic.cli.subprocess.run") as mock_run:
                            mock_run.return_value = MagicMock(returncode=0, stdout="hermes version 2.0", stderr="")

                            import io
                            from contextlib import redirect_stdout

                            output = io.StringIO()

                            with redirect_stdout(output):
                                result = _runtime_status()

        output_text = output.getvalue()

        # Should show feature statuses
        assert "Hermes version" in output_text
        assert "no_agent_cron" in output_text
        assert "supported" in output_text
        assert result == 0
