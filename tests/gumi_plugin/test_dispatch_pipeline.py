"""Tests for end-to-end checkin dispatch pipeline.

Covers:
- render_checkin_dispatch_script: globbing under cron/output/* and filtering
  of gate-only / [SILENT] outputs.
- _last_outbound_datetime: prefers state/last_outbound.json over watermark/MEMORY.md.
- dispatcher records outbound state on successful text delivery.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from relic.gumi_plugin import cron_wiring
from relic.gumi_plugin.checkin_media_dispatcher import dispatch
from relic.gumi_plugin.media_state import OUTBOUND_STATE_PATH


SUBJECT_ID = "daniele"


def _make_script(tmp_path: Path) -> Path:
    script = cron_wiring.render_checkin_dispatch_script(SUBJECT_ID)
    p = tmp_path / "dispatch.sh"
    p.write_text(script, encoding="utf-8")
    p.chmod(0o755)
    return p


def _make_diegetic_script(tmp_path: Path) -> Path:
    script = cron_wiring.render_diegetic_dispatch_script(SUBJECT_ID)
    p = tmp_path / "diegetic_dispatch.sh"
    p.write_text(script, encoding="utf-8")
    p.chmod(0o755)
    return p


def _stub_pythonpath_env(tmp_path: Path, marker: Path) -> tuple[Path, dict]:
    """Create a fake `relic.gumi_plugin.checkin_media_dispatcher` module that
    writes to `marker` when `dispatch` is invoked. Returns (stub_root, env)."""
    stub_root = tmp_path / "stubs"
    pkg = stub_root / "relic" / "gumi_plugin"
    pkg.mkdir(parents=True)
    (stub_root / "relic" / "__init__.py").write_text("", encoding="utf-8")
    (stub_root / "relic" / "gumi_plugin" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "checkin_media_dispatcher.py").write_text(
        textwrap.dedent(
            f"""
            from pathlib import Path
            def dispatch(*, llm_output, hermes_home, relic_subject_home, subject_id, force=False):
                Path({str(marker)!r}).write_text("INVOKED:" + (llm_output or ""), encoding="utf-8")
                return {{"tipo": "text", "success": True}}
            """
        ),
        encoding="utf-8",
    )
    env = {
        "HERMES_HOME": "",  # filled by caller
        "RELIC_PYTHON": sys.executable,
        "RELIC_SUBJECT_ID": SUBJECT_ID,
        "RELIC_SUBJECT_HOME": "",
        "PATH": "/usr/bin:/bin",
        "HOME": str(tmp_path),
        "PYTHONPATH": str(stub_root),
    }
    return stub_root, env


def _write_output(hermes_home: Path, job: str, content: str) -> Path:
    d = hermes_home / "cron" / "output" / job
    d.mkdir(parents=True, exist_ok=True)
    p = d / "2026-05-19_10-00.md"
    # Mimic Hermes wrapper: first line "# Cron Job: <name>", response under ## Response.
    body = f"# Cron Job: {job}\n\n**Job ID:** abc123\n\n## Response\n\n{content}\n"
    p.write_text(body, encoding="utf-8")
    return p


def test_render_checkin_dispatch_script_globs_output_root(tmp_path: Path) -> None:
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    _write_output(hermes_home, f"{SUBJECT_ID}_checkin_message", "tipo: text\nciao")

    marker = tmp_path / "marker.txt"
    _, env = _stub_pythonpath_env(tmp_path, marker)
    env["HERMES_HOME"] = str(hermes_home)
    env["RELIC_SUBJECT_HOME"] = str(tmp_path / "subj_home")

    script = _make_script(tmp_path)
    # The script hardcodes the relic_root sys.path.insert — override via PYTHONPATH
    # by stripping that line so our stub wins. Simpler: rewrite the inline python.
    text = script.read_text(encoding="utf-8")
    text = re.sub(r"sys\.path\.insert\(0, '[^']+'\)", "", text)
    script.write_text(text, encoding="utf-8")

    proc = subprocess.run(["bash", str(script)], env=env, cwd=str(tmp_path), capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert marker.exists(), f"dispatcher stub not invoked.\nSTDOUT={proc.stdout}\nSTDERR={proc.stderr}"
    assert "tipo: text" in marker.read_text(encoding="utf-8")


def test_render_checkin_dispatch_script_skips_gate_outputs(tmp_path: Path) -> None:
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    _write_output(hermes_home, f"{SUBJECT_ID}_checkin_gate", "DELIVER\ntipo: text\nciao")

    marker = tmp_path / "marker.txt"
    _, env = _stub_pythonpath_env(tmp_path, marker)
    env["HERMES_HOME"] = str(hermes_home)
    env["RELIC_SUBJECT_HOME"] = str(tmp_path / "subj_home")

    script = _make_script(tmp_path)
    text = re.sub(r"sys\.path\.insert\(0, '[^']+'\)", "", script.read_text(encoding="utf-8"))
    script.write_text(text, encoding="utf-8")

    proc = subprocess.run(["bash", str(script)], env=env, cwd=str(tmp_path), capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert not marker.exists(), "gate-only DELIVER output must not invoke dispatcher"


def test_render_checkin_dispatch_script_skips_silent(tmp_path: Path) -> None:
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    _write_output(hermes_home, f"{SUBJECT_ID}_checkin_message", "[SILENT]\n")

    marker = tmp_path / "marker.txt"
    _, env = _stub_pythonpath_env(tmp_path, marker)
    env["HERMES_HOME"] = str(hermes_home)
    env["RELIC_SUBJECT_HOME"] = str(tmp_path / "subj_home")

    script = _make_script(tmp_path)
    text = re.sub(r"sys\.path\.insert\(0, '[^']+'\)", "", script.read_text(encoding="utf-8"))
    script.write_text(text, encoding="utf-8")

    proc = subprocess.run(["bash", str(script)], env=env, cwd=str(tmp_path), capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert not marker.exists(), "[SILENT] output must not invoke dispatcher"


def test_render_diegetic_dispatch_script_reads_diegetic_message_output(tmp_path: Path) -> None:
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    _write_output(hermes_home, f"{SUBJECT_ID}_diegetic_message", "tipo: text\npiccolo frammento")

    marker = tmp_path / "marker.txt"
    _, env = _stub_pythonpath_env(tmp_path, marker)
    env["HERMES_HOME"] = str(hermes_home)
    env["RELIC_SUBJECT_HOME"] = str(tmp_path / "subj_home")
    env["RELIC_DIEGETIC_DELIVER_TARGET"] = "telegram:123456789"

    script = _make_diegetic_script(tmp_path)
    text = re.sub(r"sys\.path\.insert\(0, '[^']+'\)", "", script.read_text(encoding="utf-8"))
    script.write_text(text, encoding="utf-8")

    proc = subprocess.run(["bash", str(script)], env=env, cwd=str(tmp_path), capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert marker.exists(), f"dispatcher stub not invoked.\nSTDOUT={proc.stdout}\nSTDERR={proc.stderr}"
    assert "piccolo frammento" in marker.read_text(encoding="utf-8")
    script_text = script.read_text(encoding="utf-8")
    assert "# Cron Job: ${SUBJECT_ID}_diegetic_message" in script_text


def test_render_diegetic_dispatch_script_skips_silent(tmp_path: Path) -> None:
    hermes_home = tmp_path / "hermes"
    hermes_home.mkdir()
    _write_output(hermes_home, f"{SUBJECT_ID}_diegetic_message", "[SILENT]\n")

    marker = tmp_path / "marker.txt"
    _, env = _stub_pythonpath_env(tmp_path, marker)
    env["HERMES_HOME"] = str(hermes_home)
    env["RELIC_SUBJECT_HOME"] = str(tmp_path / "subj_home")

    script = _make_diegetic_script(tmp_path)
    text = re.sub(r"sys\.path\.insert\(0, '[^']+'\)", "", script.read_text(encoding="utf-8"))
    script.write_text(text, encoding="utf-8")

    proc = subprocess.run(["bash", str(script)], env=env, cwd=str(tmp_path), capture_output=True, text=True, timeout=30)
    assert proc.returncode == 0, proc.stderr
    assert not marker.exists(), "[SILENT] output must not invoke dispatcher"


def test_last_outbound_datetime_prefers_outbound_state(tmp_path: Path) -> None:
    hermes_home = tmp_path / "hermes"
    state = hermes_home / "state"
    state.mkdir(parents=True)

    t1 = datetime(2026, 5, 19, 10, 30, tzinfo=timezone.utc)
    t2 = datetime(2026, 5, 18, 9, 0, tzinfo=timezone.utc)

    (state / "last_outbound.json").write_text(
        json.dumps({"last_outbound_ts": t1.isoformat(), "channel": "telegram", "media_type": "text"}),
        encoding="utf-8",
    )
    (state / "memory_sync_watermark.json").write_text(
        json.dumps({"last_session_mtime_ns": int(t2.timestamp() * 1e9)}),
        encoding="utf-8",
    )
    mem = hermes_home / "MEMORY.md"
    mem.write_text("x", encoding="utf-8")

    got = cron_wiring._last_outbound_datetime(hermes_home, "")
    assert got is not None
    # tz-aware, equal instant to T1
    assert got.astimezone(timezone.utc) == t1


def test_dispatcher_records_outbound_on_text(tmp_path: Path) -> None:
    hermes_home = tmp_path / "hermes"
    relic_home = tmp_path / "relic"
    hermes_home.mkdir()
    relic_home.mkdir()

    llm_output = "tipo: text\nciao daniele"
    with patch(
        "relic.gumi_plugin.checkin_media_dispatcher._send_telegram_text",
        return_value=True,
    ):
        result = dispatch(llm_output, hermes_home, relic_home, SUBJECT_ID)

    assert result["tipo"] == "text"
    assert result.get("telegram_delivered") is True

    state_file = hermes_home / OUTBOUND_STATE_PATH
    assert state_file.exists(), "state/last_outbound.json must be written"
    data = json.loads(state_file.read_text(encoding="utf-8"))
    assert data["media_type"] == "text"
    assert data["channel"] == "telegram"
    assert "last_outbound_ts" in data


def test_dispatch_blocked_by_output_critic(tmp_path: Path) -> None:
    """Delivery-time OutputCritic suppresses dependency/need-claim output."""
    hermes_home = tmp_path / "hermes"
    relic_home = tmp_path / "relic"
    hermes_home.mkdir()
    relic_home.mkdir()

    llm_output = "tipo: text\nI need you, please don't leave me"
    with patch(
        "relic.gumi_plugin.checkin_media_dispatcher._send_telegram_text",
        return_value=True,
    ) as send:
        result = dispatch(llm_output, hermes_home, relic_home, SUBJECT_ID)

    assert result["success"] is False
    assert result["reason"] == "critic_blocked:dependency_or_need_claim"
    send.assert_not_called()  # never delivered
    assert not (hermes_home / OUTBOUND_STATE_PATH).exists()  # no outbound recorded
