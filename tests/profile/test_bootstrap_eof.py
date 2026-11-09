"""Required bootstrap prompts must stop on closed input instead of looping forever.

A blank answer is ``"\\n"``; ``readline()`` returning ``""`` means EOF. Before this,
a required prompt re-asked endlessly on EOF (e.g. ``relic subject create < /dev/null``).
"""
from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from relic.cli import main
from relic.profile._bootstrap_steps._io import prompt_required
from relic.profile._bootstrap_steps.boundaries import _collect_severity
from relic.profile._bootstrap_steps.consent import _ask_researcher_id, collect_consent_record
from relic.profile.bootstrap_tui import BootstrapTUI
from relic.profile.registry import ProfileRegistry


class _CappedInput:
    """Replays ``lines`` then reports EOF; a runaway loop fails instead of hanging."""

    def __init__(self, lines: list[str], cap: int = 200) -> None:
        self._lines = list(lines)
        self._cap = cap
        self.reads = 0

    def read(self, size: int = -1) -> str:  # makes the TUI treat this as a file-like input
        return ""

    def readline(self) -> str:
        self.reads += 1
        if self.reads > self._cap:
            raise AssertionError("prompt kept reading after EOF: infinite loop")
        return self._lines.pop(0) if self._lines else ""


def test_researcher_id_raises_on_eof():
    with pytest.raises(EOFError, match="researcher_id"):
        _ask_researcher_id(_CappedInput([]), StringIO())


def test_researcher_id_still_reprompts_on_blank_line():
    out = StringIO()
    assert _ask_researcher_id(_CappedInput(["\n", "  \n", "r1\n"]), out) == "r1"
    assert out.getvalue().count("Required field.") == 2


def test_consent_record_aborts_on_eof_at_researcher_id():
    with pytest.raises(EOFError, match="researcher_id"):
        collect_consent_record(_CappedInput(["n\n"] * 5), StringIO())


def test_prompt_required_raises_on_eof():
    with pytest.raises(EOFError, match="domain"):
        prompt_required("domain", "describe it", _CappedInput([]), StringIO())


def test_prompt_required_accepts_value_after_blank():
    assert prompt_required("domain", "d", _CappedInput(["\n", "x\n"]), StringIO()) == "x"


def test_severity_raises_on_eof():
    with pytest.raises(EOFError, match="severity"):
        _collect_severity(_CappedInput([]), StringIO())


def test_severity_reprompts_on_invalid_then_accepts():
    assert _collect_severity(_CappedInput(["nope\n", "high\n"]), StringIO()) == "high"


def test_experiment_id_raises_on_eof(tmp_path: Path):
    registry = ProfileRegistry(relic_home=tmp_path, hermes_profiles_home=tmp_path / "hp")
    tui = BootstrapTUI(registry=registry, io_in=_CappedInput(["subj_eof\n"]), io_out=StringIO())
    with pytest.raises(EOFError, match="experiment_id"):
        tui.run_init()


def test_subject_create_exits_cleanly_when_stdin_closes(tmp_path: Path, monkeypatch, capsys):
    registry = ProfileRegistry(relic_home=tmp_path / "r", hermes_profiles_home=tmp_path / "hp")
    monkeypatch.setattr("relic.cli.ProfileRegistry", lambda: registry)
    monkeypatch.setattr("sys.stdin", _CappedInput(["subj_eof\n", "exp_eof\n"], cap=2000))

    rc = main(["subject", "create"])

    assert rc == 1
    assert "researcher_id" in capsys.readouterr().err
