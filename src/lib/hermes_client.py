"""Hermes client shim for Relic OSS.

Thin wrapper around the `hermes` CLI binary.
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any


class HermesClient:
    """Thin wrapper around the `hermes` CLI binary."""

    def __init__(self, bin_path: str | None = None) -> None:
        self.bin_path = bin_path or os.environ.get("HERMES_BIN", "hermes")

    def run_profile_json(self, profile: str, message: str) -> dict[str, Any]:
        """Send a single-turn message to a Hermes profile and return a response dict.

        Returns a dict with ``payloads`` list for compatibility with callers that
        iterate over response chunks.
        """
        if not profile:
            raise ValueError("RELIC_RELATIONAL_AGENT is not configured")
        result = subprocess.run(
            [self.bin_path, "-z", message, "--profile", profile],
            capture_output=True,
            text=True,
            timeout=120,
        )
        result.check_returncode()
        text = result.stdout.strip()
        return {"response": text, "payloads": [{"text": text}]}

    def run_cron(self, cron_name: str, force: bool = True) -> None:
        """Trigger a named Hermes cron job."""
        cmd = [self.bin_path, "cron", "run", cron_name]
        if force:
            cmd.append("--force")
        subprocess.run(cmd, capture_output=True, text=True, timeout=30).check_returncode()
