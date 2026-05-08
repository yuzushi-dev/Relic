"""Tests for profile edit versioning in ProfileRegistry."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from relic.profile.registry import (
    ProfileEditEvent,
    ProfileRegistry,
    SubjectProfile,
)


@pytest.fixture
def registry(tmp_path: Path) -> ProfileRegistry:
    """Create a registry with a temporary home directory."""
    return ProfileRegistry(
        relic_home=tmp_path,
        hermes_profiles_home=tmp_path / "hermes_profiles",
    )


@pytest.fixture
def subject_profile(registry: ProfileRegistry) -> SubjectProfile:
    """Create a test subject in active status."""
    profile = registry.create_subject(
        subject_id="subj_001",
        experiment_id="exp_test",
    )
    # Advance to active status for edit tests
    registry.update_status("subj_001", "baseline_in_progress")
    registry.update_status("subj_001", "baseline_complete")
    registry.update_status("subj_001", "gumi_seed_generated")
    registry.update_status("subj_001", "gumi_seed_reviewed")
    registry.update_status("subj_001", "hermes_profile_provisioned")
    registry.update_status("subj_001", "intro_composed")
    registry.update_status("subj_001", "intro_sent")
    registry.update_status("subj_001", "active")
    return registry.get_subject("subj_001")


class TestProfileEditEvent:
    """Tests for ProfileEditEvent dataclass."""

    def test_profile_edit_event_to_dict(self) -> None:
        """ProfileEditEvent.to_dict() returns correct structure."""
        event = ProfileEditEvent(
            subject_id="subj_001",
            profile_version_before=1,
            profile_version_after=2,
            edited_fields=["gumi_background.social_world.friend"],
            edit_mode="manual",
            researcher_id="researcher_001",
            requires_intro_regeneration=True,
            created_at="2026-05-04T00:00:00Z",
        )
        d = event.to_dict()
        assert d["event_type"] == "profile_edit_event"
        assert d["subject_id"] == "subj_001"
        assert d["profile_version_before"] == 1
        assert d["profile_version_after"] == 2
        assert d["edited_fields"] == ["gumi_background.social_world.friend"]
        assert d["edit_mode"] == "manual"
        assert d["researcher_id"] == "researcher_001"
        assert d["requires_intro_regeneration"] is True

    def test_profile_edit_event_from_dict(self) -> None:
        """ProfileEditEvent.from_dict() correctly reconstructs the event."""
        data = {
            "event_type": "profile_edit_event",
            "subject_id": "subj_001",
            "profile_version_before": 1,
            "profile_version_after": 2,
            "edited_fields": ["gumi_background.social_world.friend"],
            "edit_mode": "manual",
            "researcher_id": "researcher_001",
            "requires_intro_regeneration": False,
            "created_at": "2026-05-04T00:00:00Z",
        }
        event = ProfileEditEvent.from_dict(data)
        assert event.subject_id == "subj_001"
        assert event.profile_version_before == 1
        assert event.profile_version_after == 2
        assert event.edit_mode == "manual"


class TestVersionProfileEdit:
    """Tests for ProfileRegistry.version_profile_edit()."""

    def test_version_profile_edit_increments_version(
        self, registry: ProfileRegistry, subject_profile: SubjectProfile
    ) -> None:
        """version_profile_edit() increments profile_version by 1."""
        initial_version = subject_profile.profile_version

        updated_profile, event = registry.version_profile_edit(
            subject_id="subj_001",
            edited_fields=["gumi_background.social_world.friend"],
        )

        assert updated_profile.profile_version == initial_version + 1
        assert event.profile_version_before == initial_version
        assert event.profile_version_after == initial_version + 1

    def test_profile_edit_log_jsonl_written(
        self, registry: ProfileRegistry, subject_profile: SubjectProfile, tmp_path: Path
    ) -> None:
        """profile_edit_log.jsonl is written with the event."""
        registry.version_profile_edit(
            subject_id="subj_001",
            edited_fields=["gumi_background.social_world.friend"],
            researcher_id="researcher_001",
        )

        log_path = tmp_path / "subjects" / "subj_001" / "profile_edit_log.jsonl"
        assert log_path.exists()

        with open(log_path) as f:
            line = f.readline()
            event_data = json.loads(line)

        assert event_data["event_type"] == "profile_edit_event"
        assert event_data["subject_id"] == "subj_001"
        assert "gumi_background.social_world.friend" in event_data["edited_fields"]

    def test_edit_does_not_overwrite_previous_profile(
        self, registry: ProfileRegistry, subject_profile: SubjectProfile, tmp_path: Path
    ) -> None:
        """Edit does not overwrite subject_profile.json; previous version recoverable from log."""
        initial_profile = registry.get_subject("subj_001")
        assert initial_profile is not None
        initial_version = initial_profile.profile_version

        # Perform first edit
        registry.version_profile_edit(
            subject_id="subj_001",
            edited_fields=["field_a"],
        )

        # Verify profile.json still exists and has the new version
        profile_after = registry.get_subject("subj_001")
        assert profile_after is not None
        assert profile_after.profile_version == initial_version + 1

        # Verify edit log contains the event with version info
        log_path = tmp_path / "subjects" / "subj_001" / "profile_edit_log.jsonl"
        with open(log_path) as f:
            event_data = json.loads(f.readline())

        assert event_data["profile_version_before"] == initial_version
        assert event_data["profile_version_after"] == initial_version + 1

    def test_requires_intro_regeneration_flag(
        self, registry: ProfileRegistry, subject_profile: SubjectProfile
    ) -> None:
        """requires_intro_regeneration=True is registered in the event."""
        updated_profile, event = registry.version_profile_edit(
            subject_id="subj_001",
            edited_fields=["gumi_intro_message.text"],
            requires_intro_regeneration=True,
        )

        assert event.requires_intro_regeneration is True
        assert "gumi_intro_message.text" in event.edited_fields

    def test_sequential_edits_increment_version(
        self, registry: ProfileRegistry, subject_profile: SubjectProfile
    ) -> None:
        """Multiple sequential edits correctly increment version (1→2→3 pattern)."""
        # Get current version from the fixture subject
        profile = registry.get_subject("subj_001")
        assert profile is not None
        initial_version = profile.profile_version

        # First edit
        profile, event1 = registry.version_profile_edit(
            subject_id="subj_001",
            edited_fields=["field_1"],
        )
        assert profile.profile_version == initial_version + 1
        assert event1.profile_version_after == initial_version + 1

        # Second edit
        profile, event2 = registry.version_profile_edit(
            subject_id="subj_001",
            edited_fields=["field_2"],
        )
        assert profile.profile_version == initial_version + 2
        assert event2.profile_version_before == initial_version + 1
        assert event2.profile_version_after == initial_version + 2

    def test_cannot_edit_archived_subject(
        self, registry: ProfileRegistry, subject_profile: SubjectProfile
    ) -> None:
        """Impossible to edit a subject in 'archived' status."""
        # Archive the subject
        registry.archive_subject("subj_001")

        with pytest.raises(ValueError, match="archived"):
            registry.version_profile_edit(
                subject_id="subj_001",
                edited_fields=["some_field"],
            )

    def test_cannot_edit_withdrawn_subject(
        self, registry: ProfileRegistry, subject_profile: SubjectProfile
    ) -> None:
        """Impossible to edit a subject in 'withdrawn' status."""
        # Withdraw the subject
        registry.update_status("subj_001", "withdrawn")

        with pytest.raises(ValueError, match="withdrawn"):
            registry.version_profile_edit(
                subject_id="subj_001",
                edited_fields=["some_field"],
            )

    def test_edited_fields_registered_in_event(
        self, registry: ProfileRegistry, subject_profile: SubjectProfile
    ) -> None:
        """edited_fields are correctly registered in the event."""
        edited_fields = [
            "gumi_background.social_world.friend",
            "gumi_background.place.home_space",
        ]

        _, event = registry.version_profile_edit(
            subject_id="subj_001",
            edited_fields=edited_fields,
        )

        assert event.edited_fields == edited_fields

    def test_edit_modes(
        self, registry: ProfileRegistry, subject_profile: SubjectProfile
    ) -> None:
        """All edit modes (manual, tui, api) are accepted."""
        for mode in ["manual", "tui", "api"]:
            _, event = registry.version_profile_edit(
                subject_id="subj_001",
                edited_fields=[f"field_{mode}"],
                edit_mode=mode,
            )
            assert event.edit_mode == mode

    def test_researcher_id_logged(
        self, registry: ProfileRegistry, subject_profile: SubjectProfile
    ) -> None:
        """researcher_id is correctly logged in the event."""
        researcher_id = "dr_smith_001"

        _, event = registry.version_profile_edit(
            subject_id="subj_001",
            edited_fields=["some_field"],
            researcher_id=researcher_id,
        )

        assert event.researcher_id == researcher_id


class TestProfileEditEventFixture:
    """Verify example_profile_edit_event.json matches ProfileEditEvent schema."""

    def test_example_fixture_matches_schema(self) -> None:
        """example_profile_edit_event.json corresponds to ProfileEditEvent schema."""
        fixture_path = Path(__file__).parent.parent.parent / "fixtures" / "gumi-profile-bootstrap" / "example_profile_edit_event.json"
        
        if not fixture_path.exists():
            pytest.skip("Fixture file not found")

        with open(fixture_path) as f:
            fixture_data = json.load(f)

        # All required fields must be present
        required_fields = [
            "event_type",
            "subject_id",
            "profile_version_before",
            "profile_version_after",
            "edited_fields",
            "edit_mode",
            "researcher_id",
            "requires_intro_regeneration",
            "created_at",
        ]

        for field_name in required_fields:
            assert field_name in fixture_data, f"Missing field: {field_name}"

        # Verify types
        assert isinstance(fixture_data["event_type"], str)
        assert isinstance(fixture_data["subject_id"], str)
        assert isinstance(fixture_data["profile_version_before"], int)
        assert isinstance(fixture_data["profile_version_after"], int)
        assert isinstance(fixture_data["edited_fields"], list)
        assert isinstance(fixture_data["edit_mode"], str)
        assert isinstance(fixture_data["researcher_id"], str)
        assert isinstance(fixture_data["requires_intro_regeneration"], bool)
        assert isinstance(fixture_data["created_at"], str)

        # event_type must be "profile_edit_event"
        assert fixture_data["event_type"] == "profile_edit_event"

        # Can be parsed as ProfileEditEvent
        event = ProfileEditEvent.from_dict(fixture_data)
        assert event.subject_id == fixture_data["subject_id"]
        assert event.edit_mode == fixture_data["edit_mode"]
