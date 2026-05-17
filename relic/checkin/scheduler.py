"""Check-in delivery gate: time windows, spacing, quiet hours, daily cap.

Ported from gumi_topic_gap_score.py (compute_due section).
Reads subject gumi_cron_manifest.json for per-subject overrides.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DEFAULT_TZ = ZoneInfo("Europe/Rome")

DEFAULT_WINDOWS = ["09:30-12:30", "15:00-19:30", "21:00-22:30"]
DEFAULT_QUIET_HOURS = {"start": "23:00", "end": "08:00"}
DEFAULT_MIN_SPACING_MINUTES = 240
DEFAULT_MAX_PER_DAY = 3
DEFAULT_MIN_PER_DAY = 1


def _parse_hhmm(raw: str, fallback: str = "09:00") -> time:
    src = (raw or fallback).strip()
    try:
        hh, mm = src.split(":", 1)
        return time(hour=int(hh), minute=int(mm))
    except Exception:
        hh, mm = fallback.split(":", 1)
        return time(hour=int(hh), minute=int(mm))


def _in_range_wrapped(val: time, start: time, end: time) -> bool:
    if start <= end:
        return start <= val <= end
    return val >= start or val <= end


def _in_any_window(current: time, windows: list[str]) -> bool:
    for w in windows:
        if "-" not in w:
            continue
        raw_start, raw_end = w.split("-", 1)
        s = _parse_hhmm(raw_start)
        e = _parse_hhmm(raw_end)
        if _in_range_wrapped(current, s, e):
            return True
    return False


def _quiet_hours_active(current: time, quiet_cfg: dict[str, str]) -> bool:
    s = _parse_hhmm(quiet_cfg.get("start", "23:00"))
    e = _parse_hhmm(quiet_cfg.get("end", "08:00"))
    return _in_range_wrapped(current, s, e)


def load_schedule_config(subject_id: str, relic_home: str | None = None) -> dict[str, Any]:
    """Load scheduling config from gumi_cron_manifest.json, with defaults."""
    home = Path(relic_home or os.environ.get("RELIC_HOME", Path.home() / ".relic"))
    manifest_path = home / "subjects" / subject_id / "gumi_cron_manifest.json"
    cfg: dict[str, Any] = {}
    if manifest_path.exists():
        try:
            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            cfg = raw.get("checkin_schedule", {})
        except Exception:
            pass
    return {
        "windows":              cfg.get("windows", DEFAULT_WINDOWS),
        "quiet_hours":          cfg.get("quiet_hours", DEFAULT_QUIET_HOURS),
        "min_spacing_minutes":  int(cfg.get("min_spacing_minutes", DEFAULT_MIN_SPACING_MINUTES)),
        "max_per_day":          int(cfg.get("max_per_day", DEFAULT_MAX_PER_DAY)),
        "min_per_day":          int(cfg.get("min_per_day", DEFAULT_MIN_PER_DAY)),
        "enabled":              bool(cfg.get("enabled", True)),
        "timezone":             cfg.get("timezone", "Europe/Rome"),
    }


class GateResult:
    def __init__(self, due: bool, mandatory: bool, reason: str):
        self.due = due
        self.mandatory = mandatory
        self.reason = reason

    def to_dict(self) -> dict[str, Any]:
        return {"due": self.due, "mandatory": self.mandatory, "reason": self.reason}


def check_gate(
    cfg: dict[str, Any],
    sent_today: int,
    last_sent_at: datetime | None,
    now: datetime | None = None,
) -> GateResult:
    """Return GateResult indicating whether a check-in should be sent now."""
    if not cfg.get("enabled", True):
        return GateResult(False, False, "disabled")

    tz = ZoneInfo(cfg.get("timezone", "Europe/Rome"))
    if now is None:
        now = datetime.now(tz=tz)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=tz)

    current = now.timetz().replace(tzinfo=None)

    if _quiet_hours_active(current, cfg["quiet_hours"]):
        return GateResult(False, False, "quiet_hours")

    if sent_today >= cfg["max_per_day"]:
        return GateResult(False, False, "daily_max_reached")

    if last_sent_at is not None:
        elapsed_minutes = (now - last_sent_at.astimezone(tz)).total_seconds() / 60.0
        if elapsed_minutes < cfg["min_spacing_minutes"]:
            return GateResult(False, False, "min_spacing_not_met")

    mandatory_after = time(hour=20, minute=30)
    mandatory = sent_today < cfg["min_per_day"] and current >= mandatory_after

    in_window = _in_any_window(current, cfg["windows"])
    if mandatory:
        return GateResult(True, True, "mandatory_min_target")
    if in_window:
        return GateResult(True, False, "window_due")
    return GateResult(False, False, "outside_windows")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Check if check-in is due now")
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--sent-today", type=int, default=0)
    parser.add_argument("--last-sent-at", default=None, help="ISO datetime of last send")
    parser.add_argument("--relic-home", default=None)
    args = parser.parse_args()

    from datetime import datetime
    last_sent = None
    if args.last_sent_at:
        last_sent = datetime.fromisoformat(args.last_sent_at)

    cfg = load_schedule_config(args.subject_id, args.relic_home)
    result = check_gate(cfg, args.sent_today, last_sent)
    import json
    print(json.dumps(result.to_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
