"""Tests for BootstrapTUI run_init flow (complete new input sequence)."""
from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pytest

from relic.profile.bootstrap_tui import BootstrapTUI
from relic.profile.registry import ProfileRegistry, SubjectProfile


@pytest.fixture
def registry(tmp_path: Path) -> ProfileRegistry:
    return ProfileRegistry(
        relic_home=tmp_path,
        hermes_profiles_home=tmp_path / "hermes_profiles",
    )


def make_tui(registry: ProfileRegistry, inputs: str = "") -> BootstrapTUI:
    return BootstrapTUI(registry=registry, io_in=StringIO(inputs), io_out=StringIO())


def get_output(tui: BootstrapTUI) -> str:
    return tui.io_out.getvalue()


def _make_full_inputs(
    subject_id: str | None = None,
    experiment_id: str | None = None,
    hermes: str = "yes",
    gumi_review_action: str = "accept",
    first_contact: str = "k",
    consent_researcher_id: str = "researcher_test",
    first_message_gate: str = "yes",
) -> str:
    """Build the complete input string for run_init.

    Prompt order (readline calls):
      [subject_id], only if not pre-provided to run_init()
      [experiment_id], only if not pre-provided to run_init()
      item battery (69 items), all empty → neutral/default responses
      boundaries (4 arrays + risk_flags exit + escalation_contacts exit), all empty
      consent: 5 booleans ("n")
      consent: researcher_id (required)
      consent: version (empty → "1.0.0")
      gumi_overrides: name (empty → "Gumi") + 9 domain overrides (empty → skip)
      hermes provision, yes/no
      [delivery_config], gated out when delivery consent = False
      gumi_review, accept/regenerate/abort
      first_message_gate, yes/no (should Gumi send first message?)
      [first_contact_controls], only if first_message_gate = "yes"
    """
    lines: list[str] = []
    if subject_id is not None:
        lines.append(subject_id)
    if experiment_id is not None:
        lines.append(experiment_id)
    lines.extend([""] * 49)  # structured item battery: 49 prompted items (PRO/SAFE auto-default, IOS_001 removed, INT_011 added)
    lines.extend([""] * 6)   # boundaries: 4 string arrays + risk_flags exit + escalation_contacts exit
    lines.extend(["n"] * 5)  # consent: 5 booleans (all denied)
    lines.append(consent_researcher_id)  # consent: researcher_id (required)
    lines.append("")          # consent: version (empty → "1.0.0")
    lines.append("")          # gumi name (empty → "Gumi")
    lines.extend([""] * 9)   # gumi domain overrides: 9 domains, all optional
    lines.append(hermes)      # hermes provision: yes/no
    # delivery_config: no prompts: gated out because delivery consent is False
    lines.append(gumi_review_action)     # gumi_review: accept/regenerate/abort
    lines.append(first_message_gate)     # first message gate: yes/no
    if first_message_gate.lower() in ("y", "yes"):
        lines.append(first_contact)      # first contact choice: s=send, k=keep, r=regen, e=edit, b=block
    return "\n".join(lines) + "\n"


@pytest.mark.slow
class TestRunInit:
    def test_run_init_creates_profile(self, registry: ProfileRegistry) -> None:
        inputs = _make_full_inputs(
            subject_id="subj_001",
            experiment_id="exp_001",
            hermes="yes",
        )
        tui = make_tui(registry, inputs)
        profile = tui.run_init()

        assert isinstance(profile, SubjectProfile)
        assert profile.subject_id == "subj_001"
        assert profile.experiment_id == "exp_001"
        assert profile.status == "intro_composed"
        assert profile.profile_version >= 7
        assert (profile.relic_subject_home / "gumi_background_profile.json").is_file()
        assert (profile.hermes_home / "config.yaml").is_file()
        assert (profile.relic_subject_home / "gumi_intro_message.json").is_file()
        assert (profile.relic_subject_home / "baseline_user_profile.json").is_file()
        assert (profile.relic_subject_home / "consent_record.json").is_file()

    def test_run_init_with_pre_provided_ids_skips_prompts(
        self, registry: ProfileRegistry
    ) -> None:
        inputs = _make_full_inputs(hermes="no")
        tui = make_tui(registry, inputs)
        profile = tui.run_init(subject_id="subj_002", experiment_id="exp_002")

        assert profile.subject_id == "subj_002"
        assert profile.experiment_id == "exp_002"

        output = get_output(tui)
        assert "subj_002" in output
        assert "exp_002" in output

    def test_run_init_auto_generates_subject_id_when_empty(
        self, registry: ProfileRegistry
    ) -> None:
        # subject_id="" → auto-generate; experiment_id pre-provided via run_init()
        inputs = _make_full_inputs(subject_id="", hermes="no")
        tui = make_tui(registry, inputs)
        profile = tui.run_init(experiment_id="exp_003")

        assert profile.subject_id
        assert profile.subject_id.startswith("subj_")
        output = get_output(tui)
        assert "Auto-generated subject ID" in output

    def test_run_init_logs_bootstrap_session(
        self, registry: ProfileRegistry
    ) -> None:
        inputs = _make_full_inputs(
            subject_id="subj_004",
            experiment_id="exp_004",
            hermes="yes",
        )
        tui = make_tui(registry, inputs)
        profile = tui.run_init()

        session_log = profile.relic_subject_home / "bootstrap_session.jsonl"
        assert session_log.is_file()
        content = session_log.read_text()
        assert "subject_id_entered" in content
        assert "baseline_method_selected" in content
        assert "consent_collected" in content
        assert "gumi_seed_generated" in content

    def test_run_init_consent_record_written(
        self, registry: ProfileRegistry
    ) -> None:
        inputs = _make_full_inputs(
            subject_id="subj_005",
            experiment_id="exp_005",
            hermes="yes",
            consent_researcher_id="researcher_alice",
        )
        tui = make_tui(registry, inputs)
        profile = tui.run_init()

        consent_path = profile.relic_subject_home / "consent_record.json"
        assert consent_path.is_file()
        data = json.loads(consent_path.read_text())
        assert data["recorded_by_researcher_id"] == "researcher_alice"
        assert data["delivery"] is False

    def test_run_init_baseline_artifact_written(
        self, registry: ProfileRegistry
    ) -> None:
        inputs = _make_full_inputs(
            subject_id="subj_006",
            experiment_id="exp_006",
            hermes="yes",
        )
        tui = make_tui(registry, inputs)
        profile = tui.run_init()

        baseline_path = profile.relic_subject_home / "baseline_user_profile.json"
        assert baseline_path.is_file()
        data = json.loads(baseline_path.read_text())
        assert data["subject_id"] == "subj_006"
        assert data["baseline_method"] == "structured_interview_item_battery"
        assert "item_battery" in data
        assert "self_report_fields" in data
        assert "researcher_coded_fields" in data
        assert (profile.relic_subject_home / "item_battery_response.json").is_file()


class TestFullFlow:
    def test_full_bootstrap_block_does_not_compose(
        self, registry: ProfileRegistry
    ) -> None:
        inputs = _make_full_inputs(
            subject_id="subj_block",
            experiment_id="exp_block",
            hermes="yes",
            first_contact="4",  # block → no mark_intro_composed
        )
        tui = make_tui(registry, inputs)
        profile = tui.run_init()

        assert profile.status != "intro_composed"
        output = get_output(tui)
        assert "subj_block" in output

    def test_full_bootstrap_preview_marks_intro_composed(
        self, registry: ProfileRegistry
    ) -> None:
        inputs = _make_full_inputs(
            subject_id="subj_preview",
            experiment_id="exp_preview",
            hermes="yes",
            first_contact="1",  # preview → log_event + mark_intro_composed
        )
        tui = make_tui(registry, inputs)
        profile = tui.run_init()

        assert profile.status == "intro_composed"
        assert (profile.relic_subject_home / "gumi_intro_message.json").is_file()
        assert (profile.relic_subject_home / "baseline_user_profile.json").is_file()
        assert (profile.relic_subject_home / "consent_record.json").is_file()
