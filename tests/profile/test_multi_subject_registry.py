"""Tests for ProfileRegistry — all tests use tmp_path, never ~/.relic."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure the package is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from relic.profile.registry import (
    ProfileRegistry,
    SubjectProfile,
    VALID_STATES,
    SUBJECT_DIRS,
    _REDACTED_FIELDS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def registry(tmp_path: Path) -> ProfileRegistry:
    """Fresh registry backed by a temporary directory."""
    return ProfileRegistry(
        relic_home=tmp_path,
        hermes_profiles_home=tmp_path / "hermes_profiles",
    )


# ---------------------------------------------------------------------------
# Create / List / Get
# ---------------------------------------------------------------------------

class TestCreateSubject:
    def test_default_registry_uses_relic_home_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        relic_home = tmp_path / "custom-relic-home"
        hermes_profiles_home = tmp_path / "custom-hermes-profiles"
        monkeypatch.setenv("RELIC_HOME", str(relic_home))
        monkeypatch.setenv("HERMES_PROFILES_HOME", str(hermes_profiles_home))

        registry = ProfileRegistry()

        assert registry.relic_home == relic_home
        assert registry.hermes_profiles_home == hermes_profiles_home
        assert registry.subjects_dir == relic_home / "subjects"

    def test_create_subject_returns_profile(self, registry: ProfileRegistry) -> None:
        profile = registry.create_subject("subj_001", "exp_001")
        assert profile.subject_id == "subj_001"
        assert profile.experiment_id == "exp_001"
        assert profile.status == "draft"
        assert profile.profile_version == 1
        assert profile.hermes_profile_name == "gumi-subj_001"

    def test_create_subject_creates_directory_structure(
        self, registry: ProfileRegistry
    ) -> None:
        registry.create_subject("subj_001", "exp_001")
        subject_dir = registry._subject_dir("subj_001")
        assert subject_dir.is_dir()
        for d in SUBJECT_DIRS:
            assert (subject_dir / d).is_dir()

    def test_create_subject_prepares_private_gumi_hermes_profile(
        self, registry: ProfileRegistry
    ) -> None:
        profile = registry.create_subject("subj_001", "exp_001")

        assert profile.hermes_profile_name == "gumi-subj_001"
        assert profile.hermes_home.is_dir()
        assert (profile.hermes_home / "SOUL.md").is_file()
        assert (profile.hermes_home / "USER.md").is_file()
        assert (profile.hermes_home / "MEMORY.md").is_file()

    def test_create_subject_cannot_overwrite(self, registry: ProfileRegistry) -> None:
        registry.create_subject("subj_001", "exp_001")
        with pytest.raises(ValueError, match="already exists"):
            registry.create_subject("subj_001", "exp_001")


class TestListSubjects:
    def test_list_empty(self, registry: ProfileRegistry) -> None:
        assert registry.list_subjects() == []

    def test_list_returns_all_subjects(self, registry: ProfileRegistry) -> None:
        registry.create_subject("subj_001", "exp_001")
        registry.create_subject("subj_002", "exp_001")
        subjects = registry.list_subjects()
        assert len(subjects) == 2
        ids = {s.subject_id for s in subjects}
        assert ids == {"subj_001", "subj_002"}


class TestGetSubject:
    def test_get_existing(self, registry: ProfileRegistry) -> None:
        created = registry.create_subject("subj_001", "exp_001")
        retrieved = registry.get_subject("subj_001")
        assert retrieved is not None
        assert retrieved.subject_id == created.subject_id

    def test_get_missing_returns_none(self, registry: ProfileRegistry) -> None:
        assert registry.get_subject("nonexistent") is None


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------

class TestStatusTransitions:
    def test_valid_forward_transition(
        self, registry: ProfileRegistry
    ) -> None:
        registry.create_subject("subj_001", "exp_001")
        updated = registry.update_status("subj_001", "baseline_in_progress")
        assert updated.status == "baseline_in_progress"
        assert updated.profile_version == 2

    def test_valid_transition_to_terminal(self, registry: ProfileRegistry) -> None:
        registry.create_subject("subj_001", "exp_001")
        updated = registry.update_status("subj_001", "archived")
        assert updated.status == "archived"

    def test_invalid_transition_raises(self, registry: ProfileRegistry) -> None:
        registry.create_subject("subj_001", "exp_001")
        with pytest.raises(ValueError, match="Invalid transition"):
            registry.update_status("subj_001", "active")

    def test_unknown_status_raises(self, registry: ProfileRegistry) -> None:
        registry.create_subject("subj_001", "exp_001")
        with pytest.raises(ValueError, match="Unknown status"):
            registry.update_status("subj_001", "not_a_status")

    def test_missing_subject_raises(self, registry: ProfileRegistry) -> None:
        with pytest.raises(KeyError, match="not found"):
            registry.update_status("nonexistent", "archived")


# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------

class TestArchiveSubject:
    def test_archive_sets_status(self, registry: ProfileRegistry) -> None:
        registry.create_subject("subj_001", "exp_001")
        archived = registry.archive_subject("subj_001")
        assert archived.status == "archived"

    def test_archive_missing_raises(self, registry: ProfileRegistry) -> None:
        with pytest.raises(KeyError, match="not found"):
            registry.archive_subject("nonexistent")


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------

class TestValidateSubject:
    def test_valid_new_subject(self, registry: ProfileRegistry) -> None:
        registry.create_subject("subj_001", "exp_001")
        valid, errors = registry.validate_subject("subj_001")
        assert valid is True
        assert errors == []

    def test_missing_subject(self, registry: ProfileRegistry) -> None:
        valid, errors = registry.validate_subject("nonexistent")
        assert valid is False
        assert any("not found" in e for e in errors)

    def test_missing_directories_invalid(
        self, registry: ProfileRegistry, tmp_path: Path
    ) -> None:
        # Create profile but delete provenance/ to simulate corruption
        registry.create_subject("subj_001", "exp_001")
        (registry._subject_dir("subj_001") / "provenance").rmdir()
        valid, errors = registry.validate_subject("subj_001")
        assert valid is False
        assert any("Missing directory" in e for e in errors)

    def test_unknown_status_invalid(self, registry: ProfileRegistry) -> None:
        registry.create_subject("subj_001", "exp_001")
        # Manually corrupt the status in the JSON file
        profile_path = registry._profile_path("subj_001")
        data = json.loads(profile_path.read_text())
        data["status"] = "not_a_real_status"
        profile_path.write_text(json.dumps(data))
        valid, errors = registry.validate_subject("subj_001")
        assert valid is False
        assert any("Unknown status" in e for e in errors)


# ---------------------------------------------------------------------------
# Export redacted
# ---------------------------------------------------------------------------

class TestExportRedacted:
    def test_export_creates_file(self, registry: ProfileRegistry, tmp_path: Path) -> None:
        registry.create_subject("subj_001", "exp_001")
        out_path = tmp_path / "export.json"
        result = registry.export_redacted("subj_001", out_path)
        assert result == out_path
        assert out_path.exists()

    def test_export_no_sensitive_fields(
        self, registry: ProfileRegistry, tmp_path: Path
    ) -> None:
        registry.create_subject("subj_001", "exp_001")
        out_path = tmp_path / "export.json"
        registry.export_redacted("subj_001", out_path)
        data = json.loads(out_path.read_text())
        for field in _REDACTED_FIELDS:
            assert data.get(field) == "<redacted>", f"{field} was not redacted"

    def test_export_missing_subject_raises(
        self, registry: ProfileRegistry, tmp_path: Path
    ) -> None:
        out_path = tmp_path / "export.json"
        with pytest.raises(KeyError, match="not found"):
            registry.export_redacted("nonexistent", out_path)

    def test_export_file_contains_expected_fields(
        self, registry: ProfileRegistry, tmp_path: Path
    ) -> None:
        registry.create_subject("subj_001", "exp_001")
        out_path = tmp_path / "export.json"
        registry.export_redacted("subj_001", out_path)
        data = json.loads(out_path.read_text())
        assert data["subject_id"] == "subj_001"
        assert data["experiment_id"] == "exp_001"
        assert data["status"] == "draft"
        assert "hermes_profile_name" in data
        assert data["hermes_profile_name"] == "gumi-subj_001"


# ---------------------------------------------------------------------------
# CLI smoke tests (via profile_main)
# ---------------------------------------------------------------------------

class TestCLI:
    def test_profile_main_show_missing(self) -> None:
        from relic.profile.cli import profile_main
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            reg = ProfileRegistry(
                relic_home=tmp_path,
                hermes_profiles_home=tmp_path / "hermes_profiles",
            )
            reg.create_subject("subj_001", "exp_001")
            # Monkey-patch registry so the CLI uses our temp one
            import relic.profile.cli as cli_module
            orig = None
            def make_reg() -> ProfileRegistry:
                return reg
            orig, cli_module.ProfileRegistry = cli_module.ProfileRegistry, lambda relic_home=None: reg  # type: ignore[method-assign]
            try:
                rc = profile_main(["show", "nonexistent"])
            finally:
                cli_module.ProfileRegistry = orig  # type: ignore[method-assign]
            assert rc == 1
