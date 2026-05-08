"""Tests for the top-level Relic setup command."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
import subprocess

from relic.cli import main
from relic.profile.registry import ProfileRegistry


def test_relic_setup_check_only_does_not_create_subject(
    tmp_path: Path,
    monkeypatch,
) -> None:
    registry = ProfileRegistry(
        relic_home=tmp_path / "relic",
        hermes_profiles_home=tmp_path / "hermes_profiles",
    )
    monkeypatch.setattr("relic.cli.ProfileRegistry", lambda: registry)
    out = StringIO()
    monkeypatch.setattr("sys.stdout", out)

    rc = main(["setup", "--check-only"])

    assert rc == 0
    assert registry.list_subjects() == []
    assert "then `relic subject create`" in out.getvalue()
    assert "Ollama before Hermes" in out.getvalue()


def test_relic_setup_default_does_not_create_subject(
    tmp_path: Path,
    monkeypatch,
) -> None:
    registry = ProfileRegistry(
        relic_home=tmp_path / "relic",
        hermes_profiles_home=tmp_path / "hermes_profiles",
    )
    monkeypatch.setattr("relic.cli.ProfileRegistry", lambda: registry)
    out = StringIO()
    monkeypatch.setattr("sys.stdout", out)

    rc = main(["setup"])

    assert rc == 0
    assert registry.list_subjects() == []
    assert "Setup complete." in out.getvalue()


def test_relic_setup_bootstrap_creates_venv_installs_and_relaunches(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("subprocess.run", fake_run)
    out = StringIO()
    monkeypatch.setattr("sys.stdout", out)

    rc = main(["setup", "--bootstrap", "--venv", ".venv-test"])

    assert rc == 0
    assert calls[0][:3] == ["python", "-m", "venv"]
    assert calls[1][1:4] == ["-m", "pip", "install"]
    assert calls[2][-1] == "setup"
    assert "Created virtual environment" in out.getvalue()


def test_relic_setup_guides_runtime_install_before_subject(
    tmp_path: Path,
    monkeypatch,
) -> None:
    registry = ProfileRegistry(
        relic_home=tmp_path / "relic",
        hermes_profiles_home=tmp_path / "hermes_profiles",
    )
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("relic.cli.ProfileRegistry", lambda: registry)
    monkeypatch.setattr("relic.cli.shutil.which", lambda command: None)
    monkeypatch.setattr("subprocess.run", fake_run)
    hermes_home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setattr(
        "sys.stdin",
        StringIO(
            "yes\n"  # install Ollama
            "yes\n"  # sign in
            "yes\n"  # pull starter model
            "yes\n"  # install Hermes
            "yes\n"  # configure Hermes for Ollama
            "yes\n"  # configure local Hindsight
            "\n"  # default LLM provider
            "\n"  # no Ollama API key env var
        ),
    )
    out = StringIO()
    monkeypatch.setattr("sys.stdout", out)

    rc = main(["setup", "--with-runtime", "--ollama-model", "qwen3.5:cloud"])

    assert rc == 0
    assert calls[0] == ["bash", "-lc", "curl -fsSL https://ollama.com/install.sh | sh"]
    assert calls[1] == ["ollama", "signin"]
    assert calls[2] == ["ollama", "pull", "qwen3.5:cloud"]
    assert calls[3] == [
        "bash",
        "-lc",
        "curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash",
    ]
    assert ["hermes", "config", "set", "model.provider", "custom"] in calls
    assert ["hermes", "config", "set", "model.base_url", "http://localhost:11434/v1"] in calls
    assert ["hermes", "config", "set", "model.default", "qwen3.5:cloud"] in calls
    assert ["hermes", "config", "set", "agent.tool_use_enforcement", "true"] in calls
    assert ["hermes", "config", "set", "privacy.redact_pii", "true"] in calls
    assert ["hermes", "config", "set", "memory.provider", "hindsight"] in calls
    assert ["hermes", "memory", "status"] in calls
    hindsight_config = json.loads((hermes_home / "hindsight" / "config.json").read_text())
    assert hindsight_config["mode"] == "local"
    assert hindsight_config["llm_provider"] == "ollama"
    assert hindsight_config["base_url"] == "http://localhost:11434/v1"
    assert hindsight_config["model"] == "qwen3.5:cloud"
    assert "llm_api_key" not in hindsight_config
    assert "llm_api_key_env" not in hindsight_config
    assert hindsight_config["memory_mode"] == "tools"
    assert hindsight_config["bank_id"] == "relic-local"
    assert "Ollama is configured before Hermes" in out.getvalue()
    assert "Hindsight local mode" in out.getvalue()
    assert registry.list_subjects() == []


def test_relic_setup_can_reference_ollama_api_key_env_for_hindsight(
    tmp_path: Path,
    monkeypatch,
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("relic.cli.shutil.which", lambda command: f"/usr/bin/{command}")
    monkeypatch.setattr("subprocess.run", fake_run)
    hermes_home = tmp_path / "hermes-home"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setattr(
        "sys.stdin",
        StringIO(
            "no\n"  # do not run ollama signin
            "no\n"  # do not pull starter model
            "yes\n"  # configure Hermes for Ollama
            "yes\n"  # configure local Hindsight
            "\n"  # default LLM provider
            "OLLAMA_API_KEY\n"  # optional Ollama API key env var
        ),
    )

    rc = main(["setup", "--with-runtime"])

    assert rc == 0
    hindsight_config = json.loads((hermes_home / "hindsight" / "config.json").read_text())
    assert hindsight_config["llm_provider"] == "ollama"
    assert hindsight_config["llm_api_key_env"] == "OLLAMA_API_KEY"
    assert "llm_api_key" not in hindsight_config


def test_relic_subject_create_launches_bootstrap_tui(
    tmp_path: Path,
    monkeypatch,
) -> None:
    registry = ProfileRegistry(
        relic_home=tmp_path / "relic",
        hermes_profiles_home=tmp_path / "hermes_profiles",
    )
    monkeypatch.setattr("relic.cli.ProfileRegistry", lambda: registry)
    monkeypatch.setattr("sys.stdin", StringIO("subj_001\nexp_001\n\n\n\nyes\n\n"))
    out = StringIO()
    monkeypatch.setattr("sys.stdout", out)

    rc = main(["subject", "create"])

    assert rc == 0
    profile = registry.get_subject("subj_001")
    assert profile is not None
    assert profile.status == "intro_composed"
    output = out.getvalue()
    assert "Relic Subject" in output
    assert "Use `relic profile list`" in output
