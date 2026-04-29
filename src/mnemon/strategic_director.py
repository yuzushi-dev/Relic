#!/usr/bin/env python3
"""Relic Strategic Director — weekly synthesis across all teams.

Calls Hermes Agent with the strategic-director profile (no model override,
uses the profile's own LLM config) to synthesize findings from all four
operational teams and produce a DIRECTION.md.

Cron entrypoint: relic:strategic-director
Schedule: 0 8 * * 1  (Monday 08:00 — weekly)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERMES_BIN = os.environ.get(
    "HERMES_BIN",
    str(Path.home() / ".hermes" / "hermes-agent" / "venv" / "bin" / "hermes"),
)
HERMES_PROFILE = os.environ.get("RELIC_DIRECTOR_PROFILE", "strategic-director")

TASK_PROMPT = """\
Weekly synthesis task.

Read the latest workspace digests from each of the four operational teams \
(Health Strategist, Humanness Reviewer, Biofeedback Reviewer, Inquiry Reviewer). \
Identify convergences and contradictions across findings. \
Assess scientific validity. \
Produce a DIRECTION.md with: Priority this week, Scientific Concerns, \
Humanness Trajectory, Next Cycle Objectives. \
Keep it under 400 words. Then send a 3-4 line summary to the configured Telegram channel.\
"""


def main() -> int:
    if not Path(HERMES_BIN).exists():
        print(f"ERROR: hermes not found at {HERMES_BIN}", flush=True)
        return 1

    cmd = [
        HERMES_BIN,
        "chat",
        "--profile", HERMES_PROFILE,
        "-q", TASK_PROMPT,
    ]
    data_dir = os.environ.get("RELIC_DATA_DIR", str(Path.home() / ".relic"))
    Path(data_dir).mkdir(parents=True, exist_ok=True)

    result = subprocess.run(cmd, cwd=data_dir, timeout=600)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
