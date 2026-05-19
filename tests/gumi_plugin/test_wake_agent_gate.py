"""Tests for the opt-in wakeAgent JSON gate (Plan §Task 2)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from relic.gumi_plugin.cron_wiring import render_no_agent_script


def test_rendered_script_can_emit_wake_agent_false(tmp_path: Path):
    script = render_no_agent_script(tmp_path / "relic_checkin_decision.sh")
    assert '"wakeAgent": false' in script
    assert '"wakeAgent": true' in script
    assert "RELIC_HERMES_WAKE_AGENT_JSON" in script


def test_rendered_script_json_mode_uses_stderr_for_debug(tmp_path: Path):
    script = render_no_agent_script(tmp_path / "relic_checkin_decision.sh")
    # The script must keep stdout reserved for the JSON payload in JSON mode.
    # Sanity check: there is at least one stderr redirection in the rendered
    # body so debug noise is funneled away from stdout.
    assert "file=sys.stderr" in script


def _exec_script(
    script_path: Path,
    *,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    """Execute the rendered script as a real subprocess."""
    return subprocess.run(
        ["bash", str(script_path)],
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_rendered_script_json_mode_emits_single_json_object(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    relic_home = tmp_path / "relic"
    relic_home.mkdir()

    script_path = tmp_path / "relic_checkin_decision.sh"
    script_path.write_text(render_no_agent_script(script_path), encoding="utf-8")
    script_path.chmod(0o755)

    env = {
        "RELIC_SUBJECT_ID": "subj_test",
        "RELIC_GUMI_INSTANCE_ID": "inst_test",
        "RELIC_HERMES_PROFILE_ID": "prof_test",
        "RELIC_HOME": str(relic_home),
        "RELIC_HERMES_WAKE_AGENT_JSON": "1",
        "RELIC_PYTHON": sys.executable,
    }
    # Force NO_REPLY by NOT setting HERMES_HOME / due followups — gate denies.

    result = _exec_script(script_path, env=env)
    assert result.returncode == 0, f"stderr={result.stderr}"

    # stdout must be exactly one JSON object, no extra lines.
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1, f"expected single JSON line, got {lines!r}"
    payload = json.loads(lines[0])
    assert "wakeAgent" in payload
    assert isinstance(payload["wakeAgent"], bool)
