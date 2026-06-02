"""PR22E, bootstrap scripts must not leak secrets."""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SECRETS_RE = re.compile(r"(api[_-]?key|password|token|secret)\s*[:=]", re.IGNORECASE)


def test_bootstrap_script_redacted() -> None:
    p = ROOT / "scripts" / "hermes" / "bootstrap_gumi_plugin.sh"
    assert p.exists()
    body = p.read_text()
    # Allow keyword in greps but not as assignment
    for line in body.splitlines():
        if SECRETS_RE.search(line):
            # only allowed in grep arguments
            assert "grep" in line or "fail" in line.lower(), line


def test_check_script_redacted() -> None:
    p = ROOT / "scripts" / "hermes" / "check_gumi_plugin_bootstrap.sh"
    assert p.exists()
    assert "grep -E" in p.read_text()
