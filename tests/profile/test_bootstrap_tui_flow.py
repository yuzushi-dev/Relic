"""Tests for the BootstrapTUI run_init flow.

The wizard asks ~100 questions, nearly all optional. Answers are given by looking at
the last prompt, so the tests do not break when optional questions are added, and a
wizard stuck on a required field fails (answer cap) instead of looping.

Nothing here may touch a real Hermes: ``hermes`` is hidden from ``shutil.which``, every
subprocess / ``os.system`` call is recorded and neutralised, and the gateway start is
faked. ``test_nothing_touched_real_hermes`` guards that safety net.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from io import StringIO
from pathlib import Path

import pytest

from relic.profile import bootstrap_tui
from relic.profile.bootstrap_tui import BootstrapTUI
from relic.profile.registry import ProfileRegistry, SubjectProfile


class PromptDrivenInput:
    """File-like stdin that answers each prompt from the last line the wizard printed."""

    MAX_ANSWERS = 400

    def __init__(self, out: StringIO, answers: dict[str, str] | None = None) -> None:
        self._out = out
        # substring of the prompt -> answer; anything not listed takes the default (blank)
        self._answers = {
            "researcher_id": "researcher_test",
            "Azione: accept": "accept",
            "provision a Hermes profile": "no",
            "send the first message": "no",
            **(answers or {}),
        }
        self.count = 0

    def read(self, size: int = -1) -> str:  # lets the TUI treat this as file-like
        return ""

    def readline(self) -> str:
        if self.count >= self.MAX_ANSWERS:
            raise AssertionError(
                f"wizard still asking after {self.MAX_ANSWERS} answers; "
                f"last prompt: {self._last_prompt()!r}"
            )
        self.count += 1
        prompt = self._last_prompt()
        for needle, answer in self._answers.items():
            if needle in prompt:
                return answer + "\n"
        return "\n"

    def _last_prompt(self) -> str:
        lines = self._out.getvalue().rstrip().splitlines()
        return lines[-1].strip() if lines else ""


@pytest.fixture(autouse=True)
def hermes_sandbox(monkeypatch: pytest.MonkeyPatch) -> dict[str, list]:
    """Keep the wizard away from any real Hermes: hide the binary, fake every process."""
    calls: dict[str, list] = {"subprocess": [], "gateway": []}
    real_which = shutil.which

    monkeypatch.setattr(
        shutil,
        "which",
        lambda cmd, *a, **k: None if cmd == "hermes" else real_which(cmd, *a, **k),
    )

    def fake_run(cmd, *args, **kwargs):  # type: ignore[no-untyped-def]
        calls["subprocess"].append([cmd] if isinstance(cmd, str) else list(cmd))
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        subprocess, "Popen", lambda *a, **k: pytest.fail("subprocess.Popen must not be used")
    )
    monkeypatch.setattr(os, "system", lambda cmd: calls["subprocess"].append([cmd]) or 1)
    monkeypatch.setattr(
        bootstrap_tui,
        "start_hermes_gateway_for_profile",
        lambda name, **kw: calls["gateway"].append(name) or True,
    )
    return calls


@pytest.fixture
def registry(tmp_path: Path) -> ProfileRegistry:
    return ProfileRegistry(
        relic_home=tmp_path,
        hermes_profiles_home=tmp_path / "hermes_profiles",
    )


def make_tui(registry: ProfileRegistry, answers: dict[str, str] | None = None) -> BootstrapTUI:
    out = StringIO()
    return BootstrapTUI(registry=registry, io_in=PromptDrivenInput(out, answers), io_out=out)


def get_output(tui: BootstrapTUI) -> str:
    return tui.io_out.getvalue()


def session_steps(profile: SubjectProfile) -> list[dict]:
    log = profile.relic_subject_home / "bootstrap_session.jsonl"
    return [json.loads(line) for line in log.read_text().splitlines()]


class TestRunInit:
    def test_run_init_creates_profile(self, registry: ProfileRegistry) -> None:
        tui = make_tui(
            registry,
            {
                "Enter subject ID": "subj_001",
                "Enter experiment ID": "exp_001",
                "provision a Hermes profile": "yes",
            },
        )
        profile = tui.run_init()

        assert isinstance(profile, SubjectProfile)
        assert profile.subject_id == "subj_001"
        assert profile.experiment_id == "exp_001"
        # Provisioned but never delivered: intro_composed needs a live Hermes dispatch.
        assert profile.status == "hermes_profile_provisioned"
        assert profile.profile_version > 0
        assert (profile.relic_subject_home / "gumi_background_profile.json").is_file()
        assert (profile.hermes_home / "config.yaml").is_file()
        assert (profile.relic_subject_home / "baseline_user_profile.json").is_file()
        assert (profile.relic_subject_home / "consent_record.json").is_file()

    def test_run_init_without_hermes_stops_at_gumi_seed(
        self, registry: ProfileRegistry
    ) -> None:
        profile = make_tui(registry).run_init(subject_id="subj_nh", experiment_id="exp_nh")

        assert profile.status == "gumi_seed_generated"
        assert not (profile.hermes_home / "config.yaml").exists()

    def test_run_init_with_pre_provided_ids_skips_prompts(
        self, registry: ProfileRegistry
    ) -> None:
        tui = make_tui(registry)
        profile = tui.run_init(subject_id="subj_002", experiment_id="exp_002")

        assert profile.subject_id == "subj_002"
        assert profile.experiment_id == "exp_002"
        output = get_output(tui)
        assert "subj_002" in output
        assert "exp_002" in output
        assert "Enter subject ID" not in output
        assert "Enter experiment ID" not in output

    def test_run_init_auto_generates_subject_id_when_empty(
        self, registry: ProfileRegistry
    ) -> None:
        # blank subject id answer -> auto-generate; experiment_id pre-provided
        tui = make_tui(registry)
        profile = tui.run_init(experiment_id="exp_003")

        assert profile.subject_id.startswith("subj_")
        assert "Auto-generated subject ID" in get_output(tui)

    def test_run_init_logs_bootstrap_session(self, registry: ProfileRegistry) -> None:
        tui = make_tui(registry, {"provision a Hermes profile": "yes"})
        profile = tui.run_init(subject_id="subj_004", experiment_id="exp_004")

        steps = {s["step"] for s in session_steps(profile)}
        assert {
            "subject_id_entered",
            "baseline_method_selected",
            "consent_collected",
            "gumi_seed_generated",
            "hermes_profile_provisioned",
        } <= steps

    def test_run_init_consent_record_written(self, registry: ProfileRegistry) -> None:
        tui = make_tui(registry, {"researcher_id": "researcher_alice"})
        profile = tui.run_init(subject_id="subj_005", experiment_id="exp_005")

        consent_path = profile.relic_subject_home / "consent_record.json"
        assert consent_path.is_file()
        data = json.loads(consent_path.read_text())
        assert data["recorded_by_researcher_id"] == "researcher_alice"
        assert data["delivery"] is False

    def test_run_init_baseline_artifact_written(self, registry: ProfileRegistry) -> None:
        profile = make_tui(registry).run_init(subject_id="subj_006", experiment_id="exp_006")

        baseline_path = profile.relic_subject_home / "baseline_user_profile.json"
        assert baseline_path.is_file()
        data = json.loads(baseline_path.read_text())
        assert data["subject_id"] == "subj_006"
        assert data["baseline_method"] == "structured_interview_item_battery"
        assert "item_battery" in data
        assert "self_report_fields" in data
        assert "researcher_coded_fields" in data
        assert (profile.relic_subject_home / "item_battery_response.json").is_file()


class TestFirstMessage:
    """The first message is only sent when delivery is configured; here it never is."""

    def test_first_message_without_delivery_is_blocked(
        self, registry: ProfileRegistry, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dispatched: list[str] = []
        monkeypatch.setattr(
            registry, "dispatch_intro_via_hermes", lambda sid, **kw: dispatched.append(sid)
        )
        tui = make_tui(
            registry,
            {"provision a Hermes profile": "yes", "send the first message": "yes"},
        )
        profile = tui.run_init(subject_id="subj_block", experiment_id="exp_block")

        assert dispatched == []
        assert profile.status == "hermes_profile_provisioned"
        assert "Delivery non configurato, primo messaggio non inviato." in get_output(tui)
        assert any(
            s["step"] == "first_contact_action" and s["value"] == "block"
            for s in session_steps(profile)
        )

    def test_declined_first_message_never_composes_or_sends(
        self, registry: ProfileRegistry, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            registry,
            "dispatch_intro_via_hermes",
            lambda *a, **k: pytest.fail("intro must not be dispatched"),
        )
        profile = make_tui(registry, {"provision a Hermes profile": "yes"}).run_init(
            subject_id="subj_decline", experiment_id="exp_decline"
        )

        assert profile.status not in {"intro_composed", "intro_sent", "active"}
        assert not (profile.relic_subject_home / "gumi_intro_message.json").exists()


def test_nothing_touched_real_hermes(
    registry: ProfileRegistry, hermes_sandbox: dict[str, list]
) -> None:
    """Even with provisioning accepted, no `hermes` command is ever run."""
    make_tui(registry, {"provision a Hermes profile": "yes"}).run_init(
        subject_id="subj_safe", experiment_id="exp_safe"
    )

    ran = [Path(cmd[0]).name for cmd in hermes_sandbox["subprocess"] if cmd]
    assert "hermes" not in ran
    assert hermes_sandbox["gateway"] == ["gumi-subj_safe"]  # faked, never started for real
