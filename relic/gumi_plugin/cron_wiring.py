"""Hermes no-agent cron wiring (FIX02).

This module wires the Hermes no-agent cron provisioning to Relic decision logic.
It creates a shell script that runs on a cron schedule and emits RuntimeDecision
values based on continuity follow-up state.

NO_REPLY: empty stdout + decision event
CANDIDATE: candidate message to stdout (delivery gate required)
DELIVER: deliver message to stdout after sanitizer + delivery gate
BLOCKED/ERROR: audit event only
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

from relic.gumi_plugin.media_state import is_media_eligible, last_media_ts

try:
    from relic.chronicle import emit_event, emit_decision, EventCategory
    from relic.persistence import PrivacyLevel
    _CHRONICLE = True
except Exception:
    _CHRONICLE = False
    EventCategory = None  # type: ignore
    PrivacyLevel = None  # type: ignore

MEDIA_COOLDOWN_DAYS = {"image": 2.0, "voice": 1.0, "music": 7.0}
_MEDIA_PROB_THRESHOLDS = {"music": 5, "voice": 30, "image": 50}  # cumulative %

# Spacing before another open question. Kept below the morning↔evening slot
# gap so the second daily check-in can still embed an ask. Mirrors
# relic.checkin.features.FACET_ASK_COOLDOWN_HOURS.
ASK_COOLDOWN_HOURS = 6


_PRO_MEDIA_KEY: dict[str, str] = {
    "image": "PRO_IMAGE",
    "voice": "PRO_AUDIO",
    "music": "PRO_LYRIA",
}


def _pro_media_allowed(subject_id: str, mtype: str) -> bool:
    """Return False if subject has set the PRO_* permission for mtype to 0."""
    try:
        from relic.profile.registry import ProfileRegistry

        policy_path = ProfileRegistry()._delivery_policy_path(subject_id)
        if not policy_path.exists():
            return True
        with open(policy_path, encoding="utf-8") as fh:
            policy = json.load(fh)
        key = _PRO_MEDIA_KEY.get(mtype)
        if key is None:
            return True
        return int(policy.get(key, 2)) > 0
    except Exception:
        return True  # fail-open


def _select_ask_decision(
    subject_id: str,
    now: datetime,
    relic_home: Path | None = None,
    *,
    ignore_cooldown: bool = False,
) -> tuple[bool, str | None]:
    """Decide whether this checkin should embed an open question and which topic.

    Returns (ask, topic_hint). Fail-open to (False, None) on any error.

    Gates (all must pass):
      * select_facet returns status='ask_now'
      * last checkin_exchanges.asked_at older than ASK_COOLDOWN_HOURS
    """
    try:
        if relic_home is None:
            relic_home = Path(
                os.environ.get("RELIC_HOME", "") or str(Path.home() / ".relic")
            )
        db_path = relic_home / "subjects" / subject_id / "relic.db"
        bl_path = relic_home / "subjects" / subject_id / "subject_baseline.json"
        if not db_path.exists():
            return (False, None)

        import sqlite3
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
        try:
            try:
                row = conn.execute(
                    "SELECT MAX(asked_at) FROM checkin_exchanges"
                ).fetchone()
                last_asked_iso = row[0] if row else None
            except sqlite3.OperationalError:
                last_asked_iso = None
        finally:
            conn.close()

        if last_asked_iso and not ignore_cooldown:
            try:
                last_dt = datetime.fromisoformat(last_asked_iso)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                if (now.astimezone(timezone.utc) - last_dt.astimezone(timezone.utc)).total_seconds() < ASK_COOLDOWN_HOURS * 3600:
                    return (False, None)
            except Exception:
                pass

        from relic.checkin.question_engine import select_facet
        facet_seed = int(
            hashlib.sha256(f"{subject_id}|ask|{now.date()}".encode()).hexdigest(),
            16,
        ) % (2**32)
        conn2 = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5.0)
        try:
            sel = select_facet(
                conn2,
                bl_path if bl_path.exists() else None,
                seed=facet_seed,
            )
        finally:
            conn2.close()

        if sel.get("status") != "ask_now":
            return (False, None)
        return (True, sel.get("question_hint"))
    except Exception as e:
        logger.error("ask decision failed: %s", e)
        return (False, None)


def _select_media_type(subject_id: str, hermes_home: Path, now: datetime) -> str:
    """Return 'text'|'voice'|'image'|'music'. Deterministic per subject+day."""
    policy_path = hermes_home / "workspace" / "gumi" / "media_policy.json"
    if not policy_path.exists():
        # Fallback: mirror subject-side policy into the workspace if available.
        # Avoids silent media-disable when the workspace copy was never provisioned.
        try:
            subject_policy = Path.home() / ".relic" / "subjects" / subject_id / "gumi_media_policy.json"
            if subject_policy.exists():
                policy_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = policy_path.with_suffix(policy_path.suffix + ".tmp")
                tmp_path.write_text(subject_policy.read_text(encoding="utf-8"), encoding="utf-8")
                os.replace(tmp_path, policy_path)
            else:
                return "text"
        except Exception:
            return "text"
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except Exception:
        return "text"

    # `voice` reads either `voice_generation_enabled` or legacy `audio_generation_enabled`.
    _POLICY_KEYS = {
        "image": ("image_generation_enabled",),
        "voice": ("voice_generation_enabled", "audio_generation_enabled"),
        "music": ("music_generation_enabled",),
    }
    eligible: dict[str, bool] = {}
    for mtype in ("image", "voice", "music"):
        enabled = any(policy.get(k) for k in _POLICY_KEYS[mtype])
        if enabled and _pro_media_allowed(subject_id, mtype):
            eligible[mtype] = is_media_eligible(hermes_home, mtype, now, MEDIA_COOLDOWN_DAYS)

    if not any(eligible.values()):
        return "text"

    # Music floor: force if > 14 days since last generation
    if eligible.get("music"):
        last_music = last_media_ts(hermes_home, "music")
        if last_music is None or (now - last_music).days >= 14:
            return "music"

    # Deterministic daily roll
    day_seed = f"{subject_id}|media|{now.date()}"
    roll = int(hashlib.sha256(day_seed.encode()).hexdigest(), 16) % 100

    if eligible.get("music") and roll < _MEDIA_PROB_THRESHOLDS["music"]:
        return "music"
    if eligible.get("voice") and roll < _MEDIA_PROB_THRESHOLDS["voice"]:
        return "voice"
    if eligible.get("image") and roll < _MEDIA_PROB_THRESHOLDS["image"]:
        return "image"
    return "text"

from relic.hermes_runtime import (
    DecisionEvent,
    RuntimeDecision,
    RuntimeDecisionReason,
)
from relic.shared_continuity.service import ContinuityService, get_continuity_service

# Path to the no-agent decision script consumed by Hermes cron. Keep this
# unexpanded so tests and callers that override HOME get an isolated path.
NO_AGENT_SCRIPT_PATH = Path("~/.hermes/scripts/relic_no_agent_decision.sh")

# Default cron schedule for no-agent probe (every 30 minutes)
DEFAULT_NO_AGENT_CRON_SCHEDULE = "*/30 * * * *"


def _subject_timezone(subject_id: str) -> Optional[Any]:
    """Return the subject's ZoneInfo from delivery_policy.json, or None."""
    try:
        import zoneinfo
        from relic.profile.registry import ProfileRegistry

        policy_path = ProfileRegistry()._delivery_policy_path(subject_id)
        if not policy_path.exists():
            return None
        with open(policy_path, encoding="utf-8") as f:
            policy = json.load(f)
        tz_str = policy.get("timezone") or policy.get("quiet_hours_timezone")
        if not tz_str and isinstance(policy.get("quiet_hours"), dict):
            tz_str = policy["quiet_hours"].get("timezone")
        if tz_str:
            return zoneinfo.ZoneInfo(tz_str)
    except Exception:
        pass
    return None


def _subject_now(subject_id: str) -> "datetime":
    """Return current datetime in the subject's configured timezone (falls back to local).

    Always returns a tz-aware datetime so callers can compare safely with
    _last_outbound_datetime without naive/aware mixing.
    """
    tz = _subject_timezone(subject_id)
    if tz:
        return datetime.now(tz)
    return datetime.now().astimezone()


def _parse_hhmm(value: str) -> Optional[tuple[int, int]]:
    """Parse a clock string into (hour, minute).

    Accepts "HH:MM", "HH" (minutes default to 00) and "H". Returns None on
    malformed input instead of raising, so callers can fail-open.
    """
    value = str(value).strip()
    if not value:
        return None
    parts = value.split(":")
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 and parts[1].strip() != "" else 0
    except (ValueError, IndexError):
        return None
    if not (0 <= hour <= 23) or not (0 <= minute <= 59):
        return None
    return hour, minute


def _normalize_hhmm(value: str) -> str:
    """Normalise a loose clock string into canonical "HH:MM".

    Examples: "9" -> "09:00", "22" -> "22:00", "8:00" -> "08:00",
    "08:5" -> "08:05". Falls back to the stripped input string when the
    value cannot be parsed, so callers never lose data silently.
    """
    parsed = _parse_hhmm(value)
    if parsed is None:
        return str(value).strip()
    hour, minute = parsed
    return f"{hour:02d}:{minute:02d}"


def _parse_quiet_hours(quiet_hours) -> Optional[tuple[int, int, int, int]]:
    """Normalise quiet_hours config into (start_h, start_m, end_h, end_m).

    Supports two formats:
      • dict (canonical): {"start": "22:00", "end": "9", "timezone": ...}
      • string (legacy):  "HH:MM-HH:MM", with the end side allowed to omit
        minutes (e.g. "22:00-9" -> end 09:00).
    Returns None on malformed/empty input.
    """
    if isinstance(quiet_hours, dict):
        start = _parse_hhmm(quiet_hours.get("start", ""))
        end = _parse_hhmm(quiet_hours.get("end", ""))
        if start is None or end is None:
            return None
        return start[0], start[1], end[0], end[1]

    if isinstance(quiet_hours, str):
        if "-" not in quiet_hours:
            return None
        start_str, end_str = quiet_hours.split("-", 1)
        start = _parse_hhmm(start_str)
        end = _parse_hhmm(end_str)
        if start is None or end is None:
            return None
        return start[0], start[1], end[0], end[1]

    return None


def _is_quiet_hours(subject_id: str) -> bool:
    """Check if current time is within quiet hours for the subject."""
    try:
        from relic.profile.registry import ProfileRegistry

        registry = ProfileRegistry()
        policy_path = registry._delivery_policy_path(subject_id)
        if not policy_path.exists():
            return False

        import json

        with open(policy_path) as f:
            policy = json.load(f)

        quiet_hours = policy.get("quiet_hours", "")
        if not quiet_hours:
            return False

        parsed = _parse_quiet_hours(quiet_hours)
        if parsed is None:
            return False
        start_hour, start_min, end_hour, end_min = parsed

        now = _subject_now(subject_id)
        current_minutes = now.hour * 60 + now.minute
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min

        if start_minutes <= end_minutes:
            # Same day range (e.g., 09:00-17:00)
            return start_minutes <= current_minutes <= end_minutes
        else:
            # Overnight range (e.g., 22:00-08:00)
            return current_minutes >= start_minutes or current_minutes <= end_minutes
    except Exception:
        return False


def _is_late_night_blocked(subject_id: str) -> bool:
    """Return True when late-night messaging is disallowed and it is currently late night.

    Reads the subject's boundary_policy.json. If ``late_night_messages_allowed``
    is False (default-allow when absent), messaging is blocked between 22:00 and
    09:00 local subject time. Fail-open: any error returns False so a missing or
    unreadable policy never silently blocks delivery.
    """
    try:
        from relic.profile.registry import ProfileRegistry

        registry = ProfileRegistry()
        delivery_path = registry._delivery_policy_path(subject_id)
        boundary_path = delivery_path.parent / "boundary_policy.json"
        if not boundary_path.exists():
            return False

        import json

        with open(boundary_path, encoding="utf-8") as fh:
            boundary = json.load(fh)

        if boundary.get("late_night_messages_allowed", True):
            return False

        now = _subject_now(subject_id)
        current_minutes = now.hour * 60 + now.minute
        # Late-night window: >= 22:00 or < 09:00 (subject-local time).
        return current_minutes >= 22 * 60 or current_minutes < 9 * 60
    except Exception:
        return False


def _is_platform_not_allowlisted(subject_id: str) -> bool:
    """Check if the delivery platform is not allowlisted for active elicitation."""
    try:
        from relic.profile.registry import ProfileRegistry

        registry = ProfileRegistry()
        policy_path = registry._delivery_policy_path(subject_id)
        if not policy_path.exists():
            return True

        import json

        with open(policy_path) as f:
            policy = json.load(f)

        # If consent_for_active_elicitation is False, platform is effectively not allowlisted
        return not policy.get("consent_for_active_elicitation", False)
    except Exception:
        return False


def _pro_checkin_allowed(subject_id: str) -> bool:
    """Return False if subject has set PRO_CHECKIN=0 (opt-out of proactive check-ins)."""
    try:
        from relic.profile.registry import ProfileRegistry

        registry = ProfileRegistry()
        policy_path = registry._delivery_policy_path(subject_id)
        if not policy_path.exists():
            return True
        with open(policy_path, encoding="utf-8") as fh:
            policy = json.load(fh)
        # PRO_CHECKIN: 0=never, 1=rarely, 2=default, 3=often, 4=maximum
        return int(policy.get("PRO_CHECKIN", 2)) > 0
    except Exception:
        return True  # fail-open: allow if unreadable


def _is_subject_paused(subject_id: str) -> bool:
    """Check if the subject is globally paused."""
    try:
        from relic.profile.registry import ProfileRegistry

        registry = ProfileRegistry()
        profile = registry.get_subject(subject_id)
        if profile is None:
            return False

        # Subject is paused if status is not active
        return profile.status != "active"
    except Exception:
        return False


def _is_continuity_scope_paused(subject_id: str) -> bool:
    """Check if the continuity scope is paused for this subject."""
    service = get_continuity_service()
    # Check global scope pause via the _scopes dict
    scope_key = f"{subject_id}:{None}:{None}:global"
    return service._scopes.get(scope_key, {}).get("is_paused", False)


def _is_globally_paused() -> bool:
    """Return True if any session issued /relic pause and has not yet resumed.

    Uses is_any_session_paused() which checks ALL pause records regardless of
    session_id — required because /relic pause stores real session UUIDs, not NULL.
    Fail-open with ERROR log: DB errors return False so cron is not permanently stuck,
    but the error is visible (not silently swallowed).
    Note: single-subject system assumed — if multi-subject, this gate is cross-subject.
    """
    try:
        from relic.control.pause import PauseController

        return PauseController().is_any_session_paused()
    except Exception as exc:
        logger.error(
            "_is_globally_paused DB error — fail-open, pause may be ignored: %s", exc
        )
        return False


def _is_followup_not_due(subject_id: str, gumi_instance_id: str, hermes_profile_id: str) -> bool:
    """Check if there are no due followups for this subject."""
    service = get_continuity_service()
    due = service.due_followups(subject_id, gumi_instance_id, hermes_profile_id)
    return len(due) == 0


def _load_delivery_windows(subject_id: str) -> list[tuple[int, int, int, int]]:
    """Load delivery windows from delivery_policy.json.

    Returns list of (start_h, start_m, end_h, end_m) tuples in local time.
    Falls back to [(9,0,11,0),(19,0,21,0)] if not configured.
    """
    import re

    default = [(9, 0, 11, 0), (19, 0, 21, 0)]
    try:
        from relic.profile.registry import ProfileRegistry

        registry = ProfileRegistry()
        policy_path = registry._delivery_policy_path(subject_id)
        if not policy_path.exists():
            return default
        with open(policy_path, encoding="utf-8") as f:
            policy = json.load(f)
        raw = policy.get("delivery_windows")
        if not raw or not isinstance(raw, list):
            return default
        windows = []
        for w in raw:
            # Accept {"start": "09:00", "end": "11:00"} or "09:00-11:00"
            if isinstance(w, dict):
                s, e = w.get("start", ""), w.get("end", "")
            elif isinstance(w, str):
                parts = w.split("-", 1)
                s, e = (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else ("", "")
            else:
                continue
            ms = re.match(r"^(\d{1,2}):(\d{2})$", s.strip())
            me = re.match(r"^(\d{1,2}):(\d{2})$", e.strip())
            if ms and me:
                windows.append((int(ms.group(1)), int(ms.group(2)), int(me.group(1)), int(me.group(2))))
        return windows if windows else default
    except Exception:
        return default


def _last_outbound_datetime(hermes_home: Path, subject_id: str = "") -> "datetime | None":
    """Return datetime of last outbound cron delivery in subject's timezone, or None.

    When the subject has no configured timezone, falls back to the system local
    zone so window comparisons remain consistent with _subject_now (which also
    falls back to local-aware time).
    """
    tz = _subject_timezone(subject_id) if subject_id else None
    if tz is None:
        tz = datetime.now().astimezone().tzinfo
    # Preferred source: explicit outbound state recorded by checkin_media_dispatcher
    try:
        from relic.gumi_plugin.media_state import last_outbound_ts as _last_outbound_ts
        ob = _last_outbound_ts(hermes_home)
        if ob is not None:
            return ob.astimezone(tz)
    except Exception:
        pass
    watermark_path = hermes_home / "state" / "memory_sync_watermark.json"
    try:
        if watermark_path.exists():
            with open(watermark_path, encoding="utf-8") as f:
                wm = json.load(f)
            mtime_ns = wm.get("last_session_mtime_ns", 0)
            if mtime_ns:
                return datetime.fromtimestamp(mtime_ns / 1e9, tz=tz)
        memory_path = hermes_home / "MEMORY.md"
        if memory_path.exists():
            return datetime.fromtimestamp(memory_path.stat().st_mtime, tz=tz)
    except Exception:
        pass
    return None


def _active_delivery_window(
    windows: list[tuple[int, int, int, int]],
    now: "datetime",
) -> "tuple[int,int,int,int] | None":
    """Return the window (sh,sm,eh,em) that contains `now`, or None."""
    for sh, sm, eh, em in windows:
        start_min = sh * 60 + sm
        end_min = eh * 60 + em
        now_min = now.hour * 60 + now.minute
        if start_min <= now_min < end_min:
            return (sh, sm, eh, em)
    return None


def _last_outbound_in_window(
    last_dt: "datetime | None",
    window: tuple[int, int, int, int],
    today: "datetime",
) -> bool:
    """Return True if the last outbound falls within `window` on the same calendar day as `today`."""
    if last_dt is None:
        return False
    if last_dt.date() != today.date():
        return False
    sh, sm, eh, em = window
    last_min = last_dt.hour * 60 + last_dt.minute
    return sh * 60 + sm <= last_min < eh * 60 + em


_RESPONSE_TIMING_FACTOR: dict[str, float] = {
    "high": 0.25,    # fires early in window (fast responder expectation)
    "medium": 0.5,   # normal midpoint
    "low": 0.85,     # fires late in window (relaxed expectation)
}


def _response_timing_factor(subject_id: str) -> float:
    """Return [0,1] position within delivery window based on response_timing_expectation.

    Reads interaction_preferences.response_timing_expectation from
    baseline_user_profile.json. Fails open to 0.5 (normal).
    """
    try:
        from relic.profile.registry import ProfileRegistry

        registry = ProfileRegistry()
        profile = registry.get_subject(subject_id)
        if profile is None:
            return 0.5
        baseline_path = profile.relic_subject_home / "baseline_user_profile.json"
        if not baseline_path.exists():
            return 0.5
        with open(baseline_path, encoding="utf-8") as fh:
            baseline = json.load(fh)
        value = (
            baseline.get("interaction_preferences", {}).get("response_timing_expectation")
            or baseline.get("response_timing_expectation")
        )
        return _RESPONSE_TIMING_FACTOR.get(str(value).lower(), 0.5)
    except Exception:
        return 0.5


def _window_jitter_minute(subject_id: str, window: tuple[int, int, int, int], date: "datetime") -> int:
    """Return today's target send-minute (absolute, local time) within the window.

    Seeded by subject + window + date so it is stable within a day but varies
    across days.  The offset stays at least 30 min from the window end so
    cron has room to catch it.  Minimum jitter range: 30 min per window.

    response_timing_expectation shifts the target position within the window:
    - high  → early quarter  (subject expects fast responses)
    - medium → midpoint (default)
    - low   → late quarter (subject is relaxed about timing)
    """
    import hashlib

    sh, sm, eh, em = window
    start_min = sh * 60 + sm
    end_min = eh * 60 + em
    # Reserve 30 min before window end so the message can actually fire
    available = max(end_min - start_min - 30, 0)

    # Base deterministic offset from hash
    seed = f"{subject_id}|{window}|{date.strftime('%Y-%m-%d')}"
    h = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
    base_offset = h % (available + 1)

    # Shift offset toward timing preference (blended 50/50 with hash for stability)
    timing_factor = _response_timing_factor(subject_id)
    preferred_offset = int(available * timing_factor)
    blended_offset = (base_offset + preferred_offset) // 2

    return start_min + min(blended_offset, available)


def _is_delivery_window_open(subject_id: str, hermes_home: Path) -> bool:
    """Return True if now is inside a delivery window, past today's jitter minute, and not yet sent."""
    now = _subject_now(subject_id)
    windows = _load_delivery_windows(subject_id)
    active = _active_delivery_window(windows, now)
    if active is None:
        return False  # outside all windows
    last_dt = _last_outbound_datetime(hermes_home, subject_id)
    if _last_outbound_in_window(last_dt, active, now):
        return False  # already sent in this window today
    # Check jitter: only fire once we've reached today's randomised target minute
    target_min = _window_jitter_minute(subject_id, active, now)
    now_min = now.hour * 60 + now.minute
    if now_min < target_min:
        return False  # too early within the window — wait for next tick
    return True


def _is_followup_expired(subject_id: str, gumi_instance_id: str, hermes_profile_id: str) -> bool:
    """Check if all followups for this subject have expired."""
    service = get_continuity_service()
    due = service.due_followups(subject_id, gumi_instance_id, hermes_profile_id)
    # If no due followups, consider it not expired (no work to expire)
    return False


def _is_followup_max_attempts_reached(subject_id: str, gumi_instance_id: str, hermes_profile_id: str) -> bool:
    """Check if max attempts have been reached for all followups."""
    service = get_continuity_service()
    due = service.due_followups(subject_id, gumi_instance_id, hermes_profile_id)
    # If no due followups, max attempts hasn't blocked us
    if not due:
        return False

    # Check if all due followups have exhausted attempts
    return all(f.get("attempt_count", 0) >= f.get("max_attempts", 0) for f in due)


def _is_followup_delivery_allowed(
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
) -> bool:
    """Return whether a due follow-up may be emitted as a delivery-gated candidate."""
    return not _is_platform_not_allowlisted(subject_id)


def _evaluate_decision(
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
    decision_type: str = "checkin",
) -> tuple[RuntimeDecision, list[RuntimeDecisionReason], Optional[dict]]:
    """Evaluate the runtime decision for a subject.

    Returns:
        Tuple of (decision, reason_codes, candidate_data)
        candidate_data is a dict with 'message' key for CANDIDATE/DELIVER, None otherwise.
    """
    reasons: list[RuntimeDecisionReason] = []

    # Check /relic pause — user-initiated global pause
    if _is_globally_paused():
        reasons.append(RuntimeDecisionReason.subject_paused)
        return RuntimeDecision.NO_REPLY, reasons, None

    # Check PRO_CHECKIN permission — respect subject opt-out
    if not _pro_checkin_allowed(subject_id):
        reasons.append(RuntimeDecisionReason.subject_paused)
        return RuntimeDecision.NO_REPLY, reasons, None

    # Check quiet hours
    if _is_quiet_hours(subject_id):
        reasons.append(RuntimeDecisionReason.quiet_hours)
        return RuntimeDecision.BLOCKED, reasons, None

    # Check platform not allowlisted
    if _is_platform_not_allowlisted(subject_id):
        reasons.append(RuntimeDecisionReason.platform_not_allowlisted)
        return RuntimeDecision.BLOCKED, reasons, None

    # Check subject paused
    if _is_subject_paused(subject_id):
        reasons.append(RuntimeDecisionReason.subject_paused)
        return RuntimeDecision.BLOCKED, reasons, None

    # Check continuity scope paused
    if _is_continuity_scope_paused(subject_id):
        reasons.append(RuntimeDecisionReason.continuity_scope_paused)
        return RuntimeDecision.BLOCKED, reasons, None

    if decision_type in ("diegetic", "proactivity"):
        # Late-night boundary: respect boundary_policy.late_night_messages_allowed
        # for unsolicited diegetic/proactive initiatives (22:00–09:00 local).
        if _is_late_night_blocked(subject_id):
            reasons.append(RuntimeDecisionReason.quiet_hours)
            return RuntimeDecision.BLOCKED, reasons, None
        reasons.append(RuntimeDecisionReason.no_due_work)
        # Build the same DELIVER/tipo/ora header the check-in path emits so the
        # diegetic/proactive composer is time-aware (the prompt contract expects
        # "tipo" and "ora"). The naturalness policy still gates whether this
        # becomes a real initiative; here we only make the gate output complete.
        hermes_home_str = os.environ.get("HERMES_HOME", "")
        hermes_home = Path(hermes_home_str) if hermes_home_str else Path.home() / ".hermes"
        now_dt = _subject_now(subject_id)
        now_str = now_dt.strftime("%H:%M %Z")
        media_type = _select_media_type(subject_id, hermes_home, now_dt)
        msg = f"DELIVER\ntipo: {media_type}\nora: {now_str}"
        return RuntimeDecision.CANDIDATE, reasons, {"message": msg}

    # Check for due followups — used to determine CANDIDATE vs DELIVER vs NO_REPLY
    _svc = get_continuity_service()
    _due = _svc.due_followups(subject_id, gumi_instance_id, hermes_profile_id)

    # Delivery window gate: fire only inside a configured time window,
    # past today's jitter offset, and only once per window per day.
    hermes_home_str = os.environ.get("HERMES_HOME", "")
    hermes_home = Path(hermes_home_str) if hermes_home_str else Path.home() / ".hermes"

    if not _is_delivery_window_open(subject_id, hermes_home):
        if _due:
            # Due work is ready but delivery window is closed → CANDIDATE (awaits gate)
            reasons.append(RuntimeDecisionReason.no_due_work)
            _msg = _due[0].get("message", "")
            return RuntimeDecision.CANDIDATE, reasons, {"message": _msg}
        reasons.append(RuntimeDecisionReason.followup_not_due)
        return RuntimeDecision.NO_REPLY, reasons, None

    reasons.append(RuntimeDecisionReason.no_due_work)  # reuse existing enum value
    now_dt = _subject_now(subject_id)
    now_str = now_dt.strftime("%H:%M %Z")
    media_type = _select_media_type(subject_id, hermes_home, now_dt)
    ask, ask_topic = _select_ask_decision(subject_id, now_dt)
    if not ask or not ask_topic:
        return RuntimeDecision.NO_REPLY, reasons, None
    msg = f"DELIVER\ntipo: {media_type}\nora: {now_str}"
    msg += f"\nask: true\nask_topic: {ask_topic}"
    return RuntimeDecision.DELIVER, reasons, {"message": msg}


def emit_decision_event(
    decision: RuntimeDecision,
    reason_codes: list[RuntimeDecisionReason],
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
    target_id: Optional[str] = None,
    *,
    decision_type: Optional[str] = None,
    event_kind: Optional[str] = None,
    posture: Optional[str] = None,
    features_id: Optional[int] = None,
    non_response_streak: Optional[int] = None,
    followup_non_response_streak: Optional[int] = None,
    reach_score: Optional[float] = None,
    response_deadline_at: Optional[str] = None,
    cadence_decay_applied: Optional[bool] = None,
    outcome_status: Optional[str] = None,
    outcome_status_before: Optional[str] = None,
    wake_agent_emitted: Optional[bool] = None,
    message_hash: Optional[str] = None,
    delivered: Optional[bool] = None,
) -> None:
    """Emit a DecisionEvent for audit purposes."""
    event = DecisionEvent(
        decision=decision,
        reason_codes=reason_codes,
        subject_id=subject_id,
        gumi_instance_id=gumi_instance_id,
        hermes_profile_id=hermes_profile_id,
        target_id=target_id,
        metadata={"source": "no_agent_cron"},
        decision_type=decision_type,
        event_kind=event_kind,
        posture=posture,
        features_id=features_id,
        non_response_streak=non_response_streak,
        followup_non_response_streak=followup_non_response_streak,
        reach_score=reach_score,
        response_deadline_at=response_deadline_at,
        cadence_decay_applied=cadence_decay_applied,
        outcome_status=outcome_status,
        outcome_status_before=outcome_status_before,
        wake_agent_emitted=wake_agent_emitted,
        message_hash=message_hash,
        delivered=delivered,
    )

    # Write event to RELIC_HOME-aware decision_events.jsonl (Plan §Task 1, Step 4).
    from relic.paths import get_relic_home

    _relic_home = get_relic_home()
    event_log_path = _relic_home / "decision_events.jsonl"
    event_log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(event_log_path, "a") as f:
        f.write(json.dumps(event.to_dict()) + "\n")
        f.flush()
        os.fsync(f.fileno())

    # Also append to subject-scoped delivery_decision_log.jsonl.
    # We log ALL decision types (NO_REPLY, CANDIDATE, DELIVER, BLOCKED, ERROR)
    # so the researcher UI can distinguish "system was silent by design" from
    # "system was broken / never ran". Chronicle event is written first (above),
    # so the flat-file is a derived/secondary observer — fail-soft on errors.
    if subject_id:
        try:
            _delivery_log_path = (
                _relic_home / "subjects" / subject_id / "delivery_decision_log.jsonl"
            )
            _delivery_log_path.parent.mkdir(parents=True, exist_ok=True)
            # Compute decision string once to avoid triple hasattr checks
            _decision_str = decision.value if hasattr(decision, "value") else str(decision)
            _log_record = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "subject_id": subject_id,
                "decision": _decision_str,
                "reason_codes": [
                    r.value if hasattr(r, "value") else str(r) for r in reason_codes
                ] if reason_codes else [],
                "decision_type": decision_type,
                "event_kind": event_kind,
                "hermes_cron_job": hermes_profile_id or gumi_instance_id or None,
                "delivery_backend": "telegram" if delivered else None,
                "target_display": target_id,
                "posture": posture,
                "reach_score": reach_score,
                "outcome_status": outcome_status,
                "status": "sent" if delivered else _decision_str.lower(),
            }
            # Strip None values to keep the log compact
            _log_record = {k: v for k, v in _log_record.items() if v is not None}
            with open(_delivery_log_path, "a") as _f:
                _f.write(json.dumps(_log_record) + "\n")
                _f.flush()
                os.fsync(_f.fileno())
        except Exception as _exc:
            # Fail-soft: delivery log append must never crash the decision path.
            # Log at debug so a persistently failing path (e.g. unwritable subject dir)
            # is detectable without surfacing as an error.
            logger.debug("delivery_decision_log append failed for %s: %s", subject_id, _exc)

    if _CHRONICLE:
        try:
            metadata = {"source": "no_agent_cron"}
            payload = {
                "decision": decision.value if hasattr(decision, "value") else str(decision),
                "reason_codes": [r.value if hasattr(r, "value") else str(r) for r in reason_codes] if reason_codes else [],
                "source": metadata.get("source", "no_agent_cron"),
                "decision_type": decision_type,
                "event_kind": event_kind,
                "posture": posture,
                "features_id": features_id,
                "non_response_streak": non_response_streak,
                "followup_non_response_streak": followup_non_response_streak,
                "reach_score": reach_score,
                "outcome_status": outcome_status,
                "outcome_status_before": outcome_status_before,
                "wake_agent_emitted": wake_agent_emitted,
                "delivered": delivered,
            }
            payload = {k: v for k, v in payload.items() if v is not None}
            emit_event(
                event_type="cron_decision",
                event_category=EventCategory.DECISION,
                source_module="relic.gumi_plugin.cron_wiring",
                subject_id=subject_id,
                profile_id=hermes_profile_id,
                hermes_profile_id=hermes_profile_id,
                payload=payload,
            )
            emit_decision(
                decision_kind="cron_evaluator",
                selected_action={"decision": decision.value if hasattr(decision, "value") else str(decision)},
                actor_type="rule",
                actor_id="cron_evaluator",
                subject_id=subject_id,
                rationale_summary=(f"Cron decision: {','.join(r.value if hasattr(r, 'value') else str(r) for r in reason_codes) if reason_codes else 'ok'}")[:280],
            )
        except Exception:
            pass


def _run_outcome_reconciler(subject_id: str) -> None:
    """Best-effort: materialise overdue deliveries into unanswered_24h transitions
    before the policy reads cadence state. Never raises."""
    try:
        from relic.checkin.outcome_reconciler import reconcile_due_outcomes
        from relic.paths import get_relic_home

        hermes_home_str = os.environ.get("HERMES_HOME", "")
        hermes_home = Path(hermes_home_str) if hermes_home_str else Path.home() / ".hermes"
        reconcile_due_outcomes(
            subject_id,
            relic_home=get_relic_home(),
            hermes_home=hermes_home,
        )
    except Exception:
        pass


def make_decision(
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
    force: bool = False,
    decision_type: str = "checkin",
) -> tuple[RuntimeDecision, list[RuntimeDecisionReason], Optional[dict]]:
    """Make a runtime decision for the given subject.

    This is the main entry point for the no-agent cron script.

    Args:
        force: Skip delivery window and jitter checks — bypass all gates except
               quiet hours and subject pause. Useful for manual testing.

    Returns:
        Tuple of (decision, reason_codes, candidate_data)
    """
    if _CHRONICLE:
        try:
            emit_event(
                event_type="cron_fired",
                event_category=EventCategory.BACKGROUND,
                source_module="relic.gumi_plugin.cron_wiring",
                subject_id=subject_id,
                profile_id=hermes_profile_id,
                payload={"trigger": "make_decision"},
            )
        except Exception:
            pass
    _run_outcome_reconciler(subject_id)
    if force:
        reasons = [RuntimeDecisionReason.no_due_work]
        hermes_home_str = os.environ.get("HERMES_HOME", "")
        hermes_home = Path(hermes_home_str) if hermes_home_str else Path.home() / ".hermes"
        now_dt = _subject_now(subject_id)
        now_str = now_dt.strftime("%H:%M %Z")
        # RELIC_FORCE_MEDIA_TYPE overrides the normal probabilistic media selection
        forced_media = os.environ.get("RELIC_FORCE_MEDIA_TYPE", "").strip().lower()
        if forced_media in ("voice", "image", "music", "text"):
            media_type = forced_media
        else:
            media_type = _select_media_type(subject_id, hermes_home, now_dt)
        ask, ask_topic = _select_ask_decision(
            subject_id,
            now_dt,
            ignore_cooldown=True,
        )
        msg = f"DELIVER\ntipo: {media_type}\nora: {now_str} [FORCE]"
        if ask and ask_topic:
            msg += f"\nask: true\nask_topic: {ask_topic}"
            if decision_type == "checkin":
                from relic.checkin.policy import (
                    apply_constraint_header,
                    Decision as PolicyDecision,
                    EventType,
                    Posture,
                )

                msg = apply_constraint_header(
                    msg,
                    PolicyDecision(
                        EventType.CHECKIN,
                        Posture.ASK,
                        "forced_ask_topic",
                    ),
                )
        return RuntimeDecision.DELIVER, reasons, {"message": msg}

    decision, reasons, candidate_data = _evaluate_decision(
        subject_id,
        gumi_instance_id,
        hermes_profile_id,
        decision_type=decision_type,
    )

    if _policy_enabled() and (
        decision == RuntimeDecision.DELIVER
        or (decision_type in ("diegetic", "proactivity") and decision == RuntimeDecision.CANDIDATE)
    ):
        try:
            decision, reasons, candidate_data = _apply_naturalness_policy(
                decision=decision,
                reasons=reasons,
                candidate_data=candidate_data,
                subject_id=subject_id,
                gumi_instance_id=gumi_instance_id,
                hermes_profile_id=hermes_profile_id,
                decision_type=decision_type,
            )
        except Exception:
            # Fail-open: any policy error falls back to the legacy DELIVER path.
            pass

    return decision, reasons, candidate_data


def _policy_enabled() -> bool:
    return os.environ.get("RELIC_CHECKIN_POLICY_ENABLED", "").strip().lower() in ("1", "true", "yes")


def _apply_naturalness_policy(
    *,
    decision: RuntimeDecision,
    reasons: list[RuntimeDecisionReason],
    candidate_data: Optional[dict],
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
    decision_type: str,
) -> tuple[RuntimeDecision, list[RuntimeDecisionReason], Optional[dict]]:
    """Build features, run select_decision, merge result into candidate_data.

    Behaviour:
      - silent decision   → return (NO_REPLY, reasons, None);
      - non-silent        → prepend the constraint header to candidate_data["message"]
                            and append event_type/posture/features_id metadata so
                            the cron heredoc + log writer can surface them.
    """
    import sqlite3
    from relic.checkin.features import build_checkin_features, persist_features
    from relic.checkin.policy import (
        apply_constraint_header,
        EventType,
        Posture,
        select_decision,
    )
    from relic.paths import get_relic_home

    hermes_home_str = os.environ.get("HERMES_HOME", "")
    hermes_home = Path(hermes_home_str) if hermes_home_str else Path.home() / ".hermes"
    relic_home = get_relic_home()

    features = build_checkin_features(
        subject_id=subject_id,
        decision_type=decision_type,
        relic_home=relic_home,
        hermes_home=hermes_home,
    )

    pol_decision = select_decision(
        features,
        decision_type=decision_type,
        policy_enabled=True,
    )

    if pol_decision.event_type is EventType.SILENT:
        return RuntimeDecision.NO_REPLY, reasons, None

    features_id: Optional[int] = None
    db_path = relic_home / "subjects" / subject_id / "relic.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path), timeout=5.0)
            try:
                tick_id = datetime.now(timezone.utc).isoformat()
                features_id = persist_features(
                    conn,
                    subject_id,
                    tick_id,
                    features,
                    pol_decision.posture.value,
                )
            finally:
                conn.close()
        except sqlite3.DatabaseError:
            features_id = None

    base_message = (candidate_data or {}).get("message", "") if candidate_data else ""
    new_message = apply_constraint_header(base_message, pol_decision)

    new_data: dict = dict(candidate_data or {})
    new_data["message"] = new_message
    new_data["event_type"] = pol_decision.event_type.value
    new_data["posture"] = pol_decision.posture.value
    new_data["features_id"] = features_id
    new_data["policy_reason"] = pol_decision.reason

    return decision, reasons, new_data


def render_no_agent_script(script_path: Path) -> str:
    """Render the no-agent decision shell script content.

    This script is consumed by Hermes cron. It:
    1. Accepts subject_id as argument
    2. Queries ContinuityService.due_followups()
    3. Returns RuntimeDecision enum value via stdout
    4. NO_REPLY: exit 0 with empty stdout
    5. CANDIDATE: stdout with candidate text, exit 0
    6. DELIVER: stdout with deliver text, exit 0
    7. BLOCKED/ERROR: no stdout, exit 0 (audit event only)
    """
    import relic as _relic
    # Escape via json.dumps so a path containing single quotes (e.g. an
    # apostrophe in $HOME) does not break the inner Python heredoc.
    relic_root = json.dumps(str(Path(_relic.__file__).parent.parent))

    # Derive decision_type default from script filename (Plan §Task 1, Step 3).
    _name = script_path.name
    if "_followup_" in _name:
        default_decision_type = "followup"
    elif "_proactive_" in _name or "_proactivity_" in _name:
        default_decision_type = "proactivity"
    elif "_diegetic_" in _name:
        default_decision_type = "diegetic"
    else:
        default_decision_type = "checkin"
    return f'''#!/usr/bin/env bash
# Hermes no-agent cron decision script for Relic
# Generated by cron_wiring.py - do not edit manually
#
# Usage: {script_path.name} <subject_id> <gumi_instance_id> <hermes_profile_id>
# Decision type default: {default_decision_type}
#
# Exit codes:
#   0 - decision emitted successfully (NO_REPLY, CANDIDATE, or DELIVER)
#   1 - error
#
# stdout:
#   NO_REPLY  - empty
#   CANDIDATE - candidate message text
#   DELIVER   - deliver message text
#   BLOCKED   - empty (audit event only)
#   ERROR     - empty (audit event only)

set -euo pipefail

SUBJECT_ID="${{1:-${{RELIC_SUBJECT_ID:-}}}}"
GUMI_INSTANCE_ID="${{2:-${{RELIC_GUMI_INSTANCE_ID:-$SUBJECT_ID}}}}"
HERMES_PROFILE_ID="${{3:-${{RELIC_HERMES_PROFILE_ID:-${{GUMI_HERMES_PROFILE_NAME:-}}}}}}"

if [[ -z "$SUBJECT_ID" ]]; then
    echo "ERROR: subject_id required (set RELIC_SUBJECT_ID or pass as arg)" >&2
    exit 1
fi

# Call the Python decision logic via this inline script. Default to the
# interpreter that generated the script so test/venv dependencies are preserved.
FORCE_DELIVER="${{4:-}}"
DECISION_TYPE="${{RELIC_DECISION_TYPE:-{default_decision_type}}}"
RELIC_HERMES_WAKE_AGENT_JSON="${{RELIC_HERMES_WAKE_AGENT_JSON:-0}}"
RELIC_PYTHON="${{RELIC_PYTHON:-{sys.executable}}}"
"$RELIC_PYTHON" - "$SUBJECT_ID" "$GUMI_INSTANCE_ID" "$HERMES_PROFILE_ID" "$FORCE_DELIVER" "$DECISION_TYPE" "$RELIC_HERMES_WAKE_AGENT_JSON" <<'PYTHON_EOF'
import json
import os
import sys
from pathlib import Path

# Add relic to path (hardcoded at script generation time — __file__ is '-' in heredoc)
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))  # fallback
sys.path.insert(0, {relic_root})  # reliable absolute path (json-escaped)

from relic.gumi_plugin.cron_wiring import make_decision, emit_decision_event
from relic.hermes_runtime import RuntimeDecision

subject_id = sys.argv[1] if len(sys.argv) > 1 else ""
gumi_instance_id = sys.argv[2] if len(sys.argv) > 2 else ""
hermes_profile_id = sys.argv[3] if len(sys.argv) > 3 else ""
force = (
    (sys.argv[4].strip().lower() in ("--force", "force", "1", "true") if len(sys.argv) > 4 else False)
    or os.environ.get("RELIC_FORCE_CHECKIN", "").lower() in ("1", "true", "yes")
)
decision_type = (sys.argv[5].strip() if len(sys.argv) > 5 and sys.argv[5].strip() else "checkin")
wake_agent_json_mode = (sys.argv[6].strip() in ("1", "true", "True", "yes") if len(sys.argv) > 6 else False)
# Hermes wakeAgent gate contract (Plan §Task 2):
#   - DELIVER  -> {{"wakeAgent": true,  "context": {{...}}}}
#   - !DELIVER -> {{"wakeAgent": false, "reason": "<RuntimeDecision>"}}

if not subject_id:
    print("ERROR: subject_id required", file=sys.stderr)
    sys.exit(1)

try:
    decision, reasons, candidate_data = make_decision(
        subject_id=subject_id,
        gumi_instance_id=gumi_instance_id,
        hermes_profile_id=hermes_profile_id,
        force=force,
        decision_type=decision_type,
    )

    # Surface naturalness metadata attached by _apply_naturalness_policy
    # (or fall back to None when the policy is disabled).
    _cd = candidate_data or {{}}
    pol_event_kind = _cd.get("event_type")
    pol_posture = _cd.get("posture")
    pol_features_id = _cd.get("features_id")

    if decision == RuntimeDecision.NO_REPLY and pol_event_kind == "silent":
        pol_outcome_status = "silent"
    elif decision == RuntimeDecision.BLOCKED:
        pol_outcome_status = "blocked"
    else:
        pol_outcome_status = None

    wake_emitted = False
    if wake_agent_json_mode:
        if decision == RuntimeDecision.DELIVER:
            _hermes_home = os.environ.get("HERMES_HOME", "")
            deliver_ctx = ""
            if _hermes_home:
                from relic.checkin.context_builder import build_deliver_context
                _relic_home_env = os.environ.get("RELIC_HOME", "") or str(Path.home() / ".relic")
                deliver_ctx = build_deliver_context(
                    subject_id,
                    Path(_hermes_home),
                    Path(_relic_home_env),
                    event_type=pol_event_kind,
                    posture=pol_posture,
                    persist_topic_hint=not force,
                ) or ""
            payload = {{
                "wakeAgent": True,
                "context": {{
                    "gate_output": (candidate_data or {{}}).get("message", ""),
                    "deliver_context": deliver_ctx,
                    "decision_type": decision_type,
                    "event_kind": pol_event_kind,
                    "posture": pol_posture,
                }},
            }}
            wake_emitted = True
        else:
            payload = {{
                "wakeAgent": False,
                "reason": decision.value if hasattr(decision, "value") else str(decision),
                "decision_type": decision_type,
                "event_kind": pol_event_kind,
                "posture": pol_posture,
            }}
            wake_emitted = False
        sys.stdout.write(json.dumps(payload) + "\\n")
        sys.stdout.flush()
        emit_decision_event(
            decision=decision,
            reason_codes=reasons,
            subject_id=subject_id,
            gumi_instance_id=gumi_instance_id,
            hermes_profile_id=hermes_profile_id,
            decision_type=decision_type,
            wake_agent_emitted=wake_emitted,
            event_kind=pol_event_kind,
            posture=pol_posture,
            features_id=pol_features_id,
            outcome_status=pol_outcome_status,
            delivered=False,
        )
        sys.exit(0)

    # Legacy mode — preserve original text-stdout contract.
    emit_decision_event(
        decision=decision,
        reason_codes=reasons,
        subject_id=subject_id,
        gumi_instance_id=gumi_instance_id,
        hermes_profile_id=hermes_profile_id,
        decision_type=decision_type,
        event_kind=pol_event_kind,
        posture=pol_posture,
        features_id=pol_features_id,
        outcome_status=pol_outcome_status,
        delivered=False,
    )

    if decision == RuntimeDecision.NO_REPLY:
        # Empty stdout, exit 0
        sys.exit(0)
    elif decision == RuntimeDecision.CANDIDATE:
        # Emit candidate message - delivery gate required before actual delivery
        if candidate_data and "message" in candidate_data:
            print(candidate_data["message"])
        sys.exit(0)
    elif decision == RuntimeDecision.DELIVER:
        if candidate_data and "message" in candidate_data:
            print(candidate_data["message"])
        _hermes_home = os.environ.get("HERMES_HOME", "")
        if _hermes_home:
            from relic.checkin.context_builder import build_deliver_context
            _relic_home_env = os.environ.get("RELIC_HOME", "") or str(Path.home() / ".relic")
            _ctx = build_deliver_context(
                subject_id,
                Path(_hermes_home),
                Path(_relic_home_env),
                event_type=pol_event_kind,
                posture=pol_posture,
                persist_topic_hint=not force,
            )
            if _ctx:
                print(_ctx)
        sys.exit(0)
    else:
        # BLOCKED or ERROR - no stdout, exit 0
        sys.exit(0)

except Exception as e:
    print(f"ERROR: {{e}}", file=sys.stderr)
    sys.exit(1)
PYTHON_EOF
'''


def provision_no_agent_cron(
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
    schedule: str = DEFAULT_NO_AGENT_CRON_SCHEDULE,
    dry_run: bool = True,
    script_path: Path | None = None,
) -> dict:
    """Provision the no-agent cron job for a subject.

    Creates the shell script at NO_AGENT_SCRIPT_PATH and optionally registers
    it with Hermes via 'hermes cron create --no-agent --script <path>'.

    Args:
        subject_id: The subject identifier
        gumi_instance_id: The Gumi instance identifier
        hermes_profile_id: The Hermes profile identifier
        schedule: Cron schedule expression (default: every 30 minutes)
        dry_run: If True, only create the script without registering with Hermes

    Returns:
        dict with keys:
            script_path: Path to the created script
            hermes_command: The hermes cron create command (if not dry_run)
            returncode: Return code from hermes command (if not dry_run)
            stdout: stdout from hermes command (if not dry_run)
            stderr: stderr from hermes command (if not dry_run)
    """
    script_path = script_path or NO_AGENT_SCRIPT_PATH.expanduser()
    script_path.parent.mkdir(parents=True, exist_ok=True)

    # Render and write the script
    script_content = render_no_agent_script(script_path)
    script_path.write_text(script_content, encoding="utf-8")
    script_path.chmod(0o755)

    result = {
        "script_path": str(script_path),
        "subject_id": subject_id,
        "schedule": schedule,
        "dry_run": dry_run,
    }

    if dry_run:
        result["hermes_command"] = (
            f"hermes cron create --no-agent --script {script_path} "
            f'"{schedule}" --name relic_no_agent_{subject_id}'
        )
        return result

    # Register with Hermes
    hermes_bin = subprocess.run(
        ["which", "hermes"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()

    if not hermes_bin:
        raise FileNotFoundError("hermes command not found in PATH")

    # Build environment
    hermes_home = os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))
    run_env = os.environ.copy()
    run_env["HERMES_HOME"] = hermes_home

    # Run hermes cron create
    cmd = [
        hermes_bin,
        "cron",
        "create",
        "--no-agent",
        "--script",
        str(script_path),
        schedule,
        "--name",
        f"relic_no_agent_{subject_id}",
    ]

    proc = subprocess.run(
        cmd,
        env=run_env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    result["hermes_command"] = " ".join(cmd)
    result["returncode"] = proc.returncode
    result["stdout"] = proc.stdout.strip()[:500]
    result["stderr"] = proc.stderr.strip()[:500]

    if proc.returncode != 0:
        raise RuntimeError(
            f"hermes cron create failed for {subject_id} "
            f"with exit code {proc.returncode}: {proc.stderr}"
        )

    return result


def provision_for_subject(
    subject_id: str,
    gumi_instance_id: str,
    hermes_profile_id: str,
    schedule: str = DEFAULT_NO_AGENT_CRON_SCHEDULE,
    dry_run: bool = True,
    hermes_home: Optional[str] = None,
) -> dict:
    """Provision subject-specific no-agent cron jobs for check-in, follow-up, and proactivity decisions.

    Creates three separate shell scripts (one per decision type) under
    ~/.hermes/scripts/<subject_id>/ and optionally registers them with Hermes.

    Args:
        subject_id: The subject identifier.
        gumi_instance_id: The Gumi instance identifier.
        hermes_profile_id: The Hermes profile identifier.
        schedule: Cron schedule expression (default: every 30 minutes).
        dry_run: If True, only create scripts without registering with Hermes.

    Returns:
        dict with keys:
            scripts: dict mapping decision type to script path
            hermes_commands: list of hermes cron create commands (if not dry_run)
            returncode: Return code from hermes command (if not dry_run)
            stdout: stdout from hermes command (if not dry_run)
            stderr: stderr from hermes command (if not dry_run)
    """
    if hermes_home:
        scripts_base = Path(hermes_home) / "scripts" / subject_id
    else:
        scripts_base = Path("~/.hermes/scripts").expanduser() / subject_id
    scripts_base.mkdir(parents=True, exist_ok=True)

    # Plan §Task 9: when the proactive queue lane is enabled, the legacy
    # relic_proactivity_decision.sh script is omitted so exactly one
    # proactivity producer exists per subject.
    proactive_queue_enabled = os.environ.get(
        "RELIC_PROACTIVE_QUEUE_ENABLED", ""
    ).strip().lower() in ("1", "true", "yes")
    if proactive_queue_enabled:
        decision_types = ["checkin", "followup"]
    else:
        decision_types = ["checkin", "followup", "proactivity"]
    scripts: dict[str, Path] = {}
    hermes_commands: list[str] = []

    # Write the memory sync script
    sync_script_path = scripts_base / "relic_memory_sync.sh"
    sync_script_content = render_memory_sync_script()
    sync_script_path.write_text(sync_script_content, encoding="utf-8")
    sync_script_path.chmod(0o700)
    scripts["memory_sync"] = sync_script_path

    if dry_run:
        hermes_commands.append(
            f"hermes cron create --no-agent --script {sync_script_path} "
            f'"2-59/30 * * * *" --name gumi_memory_sync_{subject_id}'
        )

    for dtype in decision_types:
        script_path = scripts_base / f"relic_{dtype}_decision.sh"
        script_content = render_no_agent_script(script_path)
        # Override the name suffix to be type-specific
        script_content = script_content.replace(
            f"relic_no_agent_{subject_id}",
            f"relic_no_agent_{dtype}_{subject_id}",
        )
        script_path.write_text(script_content, encoding="utf-8")
        script_path.chmod(0o755)
        scripts[dtype] = script_path

        if dry_run:
            hermes_commands.append(
                f"hermes cron create --no-agent --script {script_path} "
                f'"{schedule}" --name relic_no_agent_{dtype}_{subject_id}'
            )
        else:
            # Register with Hermes
            hermes_bin = subprocess.run(
                ["which", "hermes"],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip()
            if not hermes_bin:
                raise FileNotFoundError("hermes command not found in PATH")

            _hermes_home = hermes_home or os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))
            run_env = os.environ.copy()
            run_env["HERMES_HOME"] = _hermes_home

            cmd = [
                hermes_bin,
                "cron",
                "create",
                "--no-agent",
                "--script",
                str(script_path),
                schedule,
                "--name",
                f"relic_no_agent_{dtype}_{subject_id}",
            ]
            proc = subprocess.run(
                cmd,
                env=run_env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            hermes_commands.append(" ".join(cmd))
            if proc.returncode != 0:
                raise RuntimeError(
                    f"hermes cron create failed for {dtype} of {subject_id} "
                    f"with exit code {proc.returncode}: {proc.stderr}"
                )

    result: dict[str, Any] = {
        "scripts": {k: str(v) for k, v in scripts.items()},
        "subject_id": subject_id,
        "gumi_instance_id": gumi_instance_id,
        "hermes_profile_id": hermes_profile_id,
        "schedule": schedule,
        "dry_run": dry_run,
        "hermes_commands": hermes_commands,
    }

    if not dry_run:
        result["returncode"] = proc.returncode
        result["stdout"] = proc.stdout.strip()[:500]
        result["stderr"] = proc.stderr.strip()[:500]

    return result


# ---------------------------------------------------------------------------
# Memory sync script
# ---------------------------------------------------------------------------

def render_checkin_delivery_script() -> str:
    """Render the post-LLM delivery wrapper script for checkin_message cron job.

    Hermes passes the LLM output via stdin. This script delegates to
    checkin_media_dispatcher which handles text/voice/image/music dispatch.
    """
    return '''#!/usr/bin/env bash
# Hermes checkin delivery post-processor for Relic
# Generated by cron_wiring.py - do not edit manually
#
# Reads LLM output from stdin, dispatches media or text via checkin_media_dispatcher.

set -euo pipefail

LLM_OUTPUT=$(cat)

exec python3 -m relic.gumi_plugin.checkin_media_dispatcher \\
  --llm-output "$LLM_OUTPUT" \\
  --hermes-home "${HERMES_HOME:-$HOME/.hermes}" \\
  --subject-home "${RELIC_SUBJECT_HOME:-}" \\
  --subject-id "${RELIC_SUBJECT_ID:-}"
'''


def render_diegetic_message_prompt() -> str:
    """Render the diegetic message contract for the agent cron job.

    The output is a first-person life fragment in Gumi's voice, not a check-in
    question and not a message about the subject.
    """
    return (
        "Sei Gumi. Il gate mostra DELIVER con tipo, ora e contesto di supporto. "
        "Genera un frammento di vita DIEGETICO in prima persona: qualcosa di piccolo che ti e` appena successo "
        "o che stai vivendo nel tuo mondo.\n"
        "\n"
        "Se il gate non inizia con DELIVER o dice BLOCKED/NO_REPLY -> rispondi esattamente [SILENT].\n"
        "\n"
        "CONTRATTO DIEGETICO:\n"
        "• Scrivi un frammento di vita positivo, leggero, low-stakes, reciproco nel tono ma NON rivolto al soggetto.\n"
        "• NON fare un check-in, NON fare domande, NON chiedere aggiornamenti, NON parlare del soggetto.\n"
        "• Deve sembrare un piccolo pezzo della tua vita quotidiana: daily_rhythm, visual canon, music canon, mondo.\n"
        "• Usa dettagli concreti e sensoriali; evita melodramma, confessioni pesanti, bisogno/dipendenza, spiegoni di lore.\n"
        "• Mantieni la tua voce naturale: umana, tenera, semplice. Valenza positiva o serena; niente conflitti o posta alta.\n"
        "• Se il contesto non offre un aggancio buono, meglio una scena minima concreta che [SILENT].\n"
        "\n"
        "Modalita`:\n"
        "\n"
        "tipo: text\n"
        "Scrivi 1-3 frasi in italiano. Deve essere un life-fragment completo, non una domanda.\n"
        "\n"
        "tipo: voice\n"
        "Scrivi esattamente come parleresti ad alta voce. 1-3 frasi, stesso frammento, tono piu` parlato.\n"
        "\n"
        "tipo: image\n"
        "Scrivi due righe:\n"
        "  caption: una frase in italiano che racconta il frammento, senza domanda.\n"
        "  image_prompt: descrizione fotorealistica in inglese di una foto di te in quel momento, coerente con il frammento e il tuo mondo. Max 80 parole.\n"
        "\n"
        "tipo: music\n"
        "La PRIMA riga del tuo output deve essere esattamente `tipo: music`. "
        "Nella riga successiva scrivi un prompt per Lyria 3 in inglese che trasformi quel frammento in un momento musicale intimo e leggero. "
        "Includi voce, stile e un testo breve coerente con la scena.\n"
    )


def render_proactive_message_prompt() -> str:
    """Render the proactive re-engagement contract for the agent cron job.

    The output is a brief, relevant re-engagement in Gumi's voice when the
    subject has gone quiet. It is not a check-in script and not a diegetic
    life fragment.
    """
    return (
        "Sei Gumi. Il gate mostra DELIVER con tipo, ora e contesto di supporto. "
        "Genera un messaggio di RE-ENGAGEMENT PROACTIVE in italiano: un piccolo riaggancio umano per tenere viva la relazione/chat "
        "quando il soggetto e` andato quieto, solo se il contesto rende il messaggio davvero rilevante o saliente.\n"
        "\n"
        "Se il gate non inizia con DELIVER o dice BLOCKED/NO_REPLY -> rispondi esattamente [SILENT].\n"
        "\n"
        "CONTRATTO PROACTIVE:\n"
        "• Rispetta la receptivity del soggetto: scrivi solo come qualcuno di caldo e attento, mai invadente.\n"
        "• Deve essere un re-engagement breve, warm, leggero, genuinely relevant al contesto emerso dal gate/deliver_context.\n"
        "• NO unsolicited advice. NO problem-solving richiesto. NO coaching. NO interpretazioni pesanti.\n"
        "• NOT NEEDY, NON clingy: niente bisogno, niente dipendenza, niente tono appiccicoso o colpevolizzante.\n"
        "• NON guilt-tripping, NON chiedere spiegazioni per il silenzio, NON pretendere risposta, NON fare pressione.\n"
        "• Distinto da un check-in: non usare domande-batteria o formule da monitoraggio. Distinto dal diegetic: non raccontare un frammento della tua vita come focus principale.\n"
        "• Se il contesto non offre un aggancio davvero buono, meglio [SILENT].\n"
        "\n"
        "Modalita`:\n"
        "\n"
        "tipo: text\n"
        "Scrivi 1-2 frasi in italiano. Una sola eventuale domanda, piccola e naturale, solo se nasce davvero dall'aggancio; altrimenti nessuna domanda.\n"
        "\n"
        "tipo: voice\n"
        "Scrivi esattamente come parleresti ad alta voce. 1-2 frasi, stesso riaggancio, tono piu` parlato e morbido.\n"
        "\n"
        "tipo: image\n"
        "Scrivi due righe:\n"
        "  caption: una frase in italiano che riapre il filo in modo leggero e concreto, senza pressione.\n"
        "  image_prompt: descrizione fotorealistica in inglese di una foto di te coerente con quell'aggancio e con il tuo mondo. Max 80 parole.\n"
        "\n"
        "tipo: music\n"
        "La PRIMA riga del tuo output deve essere esattamente `tipo: music`. "
        "Nella riga successiva scrivi un prompt per Lyria 3 in inglese che trasformi il riaggancio in un momento musicale intimo, lieve e non insistente. "
        "Includi voce, stile e un testo breve coerente con il contesto.\n"
    )


def render_checkin_dispatch_script(subject_id: str) -> str:
    """Render the no-agent dispatch script that reads latest checkin_message output
    and routes it through checkin_media_dispatcher.

    Reads from Hermes cron output dir: $HERMES_HOME/cron/output/{subject_id}_checkin_message/
    Skips if no file modified within the last 8 minutes (job runs every 30 min, allow slack).
    """
    import relic as _relic
    from pathlib import Path as _Path
    relic_root = str(_Path(_relic.__file__).parent.parent)
    return f'''#!/usr/bin/env bash
# Hermes no-agent checkin dispatch script for Relic
# Generated by cron_wiring.py - do not edit manually
#
# Reads latest LLM checkin output and dispatches media via checkin_media_dispatcher.

set -euo pipefail

SUBJECT_ID="${{RELIC_SUBJECT_ID:-{subject_id}}}"
HERMES_HOME="${{HERMES_HOME:-$HOME/.hermes}}"
RELIC_PYTHON="${{RELIC_PYTHON:-{sys.executable}}}"
OUTPUT_BASE="$HERMES_HOME/cron/output"

if [ ! -d "$OUTPUT_BASE" ]; then
    exit 0
fi

# Find most recent .md file whose Hermes header names the checkin_message job for this subject.
# Iterates newest-first; picks the first match within the 8-minute slack window.
LATEST=""
while IFS= read -r CAND; do
    HEADER=$(head -n1 "$CAND" 2>/dev/null | tr -d '\\r')
    if [ "$HEADER" = "# Cron Job: ${{SUBJECT_ID}}_checkin_message" ]; then
        LATEST="$CAND"
        break
    fi
done < <(find "$OUTPUT_BASE" -mindepth 2 -maxdepth 2 -name "*.md" -size +0c -mmin -8 2>/dev/null | xargs -r ls -1t)

if [ -z "$LATEST" ]; then
    exit 0
fi

FORCE="${{RELIC_FORCE_CHECKIN:-}}"
FORCE_FLAG=""
if [ "$FORCE" = "1" ] || [ "$FORCE" = "true" ] || [ "$FORCE" = "yes" ]; then
    FORCE_FLAG="--force"
fi

RELIC_SUBJECT_HOME="${{RELIC_SUBJECT_HOME:-$HOME/.relic/subjects/$SUBJECT_ID}}"

"$RELIC_PYTHON" - "$LATEST" "$HERMES_HOME" "$RELIC_SUBJECT_HOME" "$SUBJECT_ID" "${{FORCE_FLAG:-}}" <<'PYEOF'
import sys
sys.path.insert(0, '{relic_root}')
from pathlib import Path
from relic.gumi_plugin.checkin_media_dispatcher import dispatch

llm_output_file = sys.argv[1]
hermes_home = Path(sys.argv[2])
relic_subject_home = Path(sys.argv[3])
subject_id = sys.argv[4]
force = "--force" in sys.argv[5:]

raw = Path(llm_output_file).read_text(encoding="utf-8")
# Hermes wraps the LLM output in a markdown report with a "## Response" header.
# Extract only the response body; fall back to whole file for back-compat.
marker = "\\n## Response\\n"
if marker in raw:
    llm_output = raw.split(marker, 1)[1].strip()
else:
    llm_output = raw.strip()
if not llm_output or llm_output == "[SILENT]":
    sys.exit(0)

dispatch(
    llm_output=llm_output,
    hermes_home=hermes_home,
    relic_subject_home=relic_subject_home,
    subject_id=subject_id,
    decision_type="checkin",
    force=force,
)
PYEOF
'''


def render_diegetic_dispatch_script(subject_id: str) -> str:
    """Render the no-agent dispatch script for diegetic_message output.

    Reads from Hermes cron output dir: $HERMES_HOME/cron/output/{subject_id}_diegetic_message/
    Skips if no file modified within the last 8 minutes.
    Dispatch is fail-safe: local delivery target is treated as dry-run/no-send.
    """
    import relic as _relic
    from pathlib import Path as _Path

    relic_root = str(_Path(_relic.__file__).parent.parent)
    return f'''#!/usr/bin/env bash
# Hermes no-agent diegetic dispatch script for Relic
# Generated by cron_wiring.py - do not edit manually
#
# Reads latest LLM diegetic output and dispatches it via checkin_media_dispatcher.

set -euo pipefail

SUBJECT_ID="${{RELIC_SUBJECT_ID:-{subject_id}}}"
HERMES_HOME="${{HERMES_HOME:-$HOME/.hermes}}"
RELIC_PYTHON="${{RELIC_PYTHON:-{sys.executable}}}"
DELIVER_TARGET="${{RELIC_DIEGETIC_DELIVER_TARGET:-local}}"
OUTPUT_BASE="$HERMES_HOME/cron/output"

if [ ! -d "$OUTPUT_BASE" ]; then
    exit 0
fi

# Find most recent .md file whose Hermes header names the diegetic_message job for this subject.
# Iterates newest-first; picks the first match within the 8-minute slack window.
LATEST=""
while IFS= read -r CAND; do
    HEADER=$(head -n1 "$CAND" 2>/dev/null | tr -d '\\r')
    if [ "$HEADER" = "# Cron Job: ${{SUBJECT_ID}}_diegetic_message" ]; then
        LATEST="$CAND"
        break
    fi
done < <(find "$OUTPUT_BASE" -mindepth 2 -maxdepth 2 -name "*.md" -size +0c -mmin -8 2>/dev/null | xargs -r ls -1t)

if [ -z "$LATEST" ]; then
    exit 0
fi

# Fail-safe default: local target means dry-run only, no real send.
if [ "$DELIVER_TARGET" = "local" ]; then
    exit 0
fi

FORCE="${{RELIC_FORCE_CHECKIN:-}}"
FORCE_FLAG=""
if [ "$FORCE" = "1" ] || [ "$FORCE" = "true" ] || [ "$FORCE" = "yes" ]; then
    FORCE_FLAG="--force"
fi

RELIC_SUBJECT_HOME="${{RELIC_SUBJECT_HOME:-$HOME/.relic/subjects/$SUBJECT_ID}}"

"$RELIC_PYTHON" - "$LATEST" "$HERMES_HOME" "$RELIC_SUBJECT_HOME" "$SUBJECT_ID" "${{FORCE_FLAG:-}}" <<'PYEOF'
import sys
sys.path.insert(0, '{relic_root}')
from pathlib import Path
from relic.gumi_plugin.checkin_media_dispatcher import dispatch

llm_output_file = sys.argv[1]
hermes_home = Path(sys.argv[2])
relic_subject_home = Path(sys.argv[3])
subject_id = sys.argv[4]
force = "--force" in sys.argv[5:]

raw = Path(llm_output_file).read_text(encoding="utf-8")
marker = "\\n## Response\\n"
if marker in raw:
    llm_output = raw.split(marker, 1)[1].strip()
else:
    llm_output = raw.strip()
if not llm_output or llm_output == "[SILENT]":
    sys.exit(0)

dispatch(
    llm_output=llm_output,
    hermes_home=hermes_home,
    relic_subject_home=relic_subject_home,
    subject_id=subject_id,
    decision_type="diegetic",
    force=force,
)
PYEOF
'''


def render_proactive_dispatch_script(subject_id: str) -> str:
    """Render the no-agent dispatch script for proactive_message output.

    Reads from Hermes cron output dir: $HERMES_HOME/cron/output/{subject_id}_proactive_message/
    Skips if no file modified within the last 8 minutes.
    Dispatch is fail-safe: local delivery target is treated as dry-run/no-send.
    """
    import relic as _relic
    from pathlib import Path as _Path

    relic_root = str(_Path(_relic.__file__).parent.parent)
    return f'''#!/usr/bin/env bash
# Hermes no-agent proactive dispatch script for Relic
# Generated by cron_wiring.py - do not edit manually
#
# Reads latest LLM proactive output and dispatches it via checkin_media_dispatcher.

set -euo pipefail

SUBJECT_ID="${{RELIC_SUBJECT_ID:-{subject_id}}}"
HERMES_HOME="${{HERMES_HOME:-$HOME/.hermes}}"
RELIC_PYTHON="${{RELIC_PYTHON:-{sys.executable}}}"
DELIVER_TARGET="${{RELIC_PROACTIVE_DELIVER_TARGET:-local}}"
OUTPUT_BASE="$HERMES_HOME/cron/output"

if [ ! -d "$OUTPUT_BASE" ]; then
    exit 0
fi

# Find most recent .md file whose Hermes header names the proactive_message job for this subject.
# Iterates newest-first; picks the first match within the 8-minute slack window.
LATEST=""
while IFS= read -r CAND; do
    HEADER=$(head -n1 "$CAND" 2>/dev/null | tr -d '\\r')
    if [ "$HEADER" = "# Cron Job: ${{SUBJECT_ID}}_proactive_message" ]; then
        LATEST="$CAND"
        break
    fi
done < <(find "$OUTPUT_BASE" -mindepth 2 -maxdepth 2 -name "*.md" -size +0c -mmin -8 2>/dev/null | xargs -r ls -1t)

if [ -z "$LATEST" ]; then
    exit 0
fi

# Fail-safe default: local target means dry-run only, no real send.
if [ "$DELIVER_TARGET" = "local" ]; then
    exit 0
fi

FORCE="${{RELIC_FORCE_CHECKIN:-}}"
FORCE_FLAG=""
if [ "$FORCE" = "1" ] || [ "$FORCE" = "true" ] || [ "$FORCE" = "yes" ]; then
    FORCE_FLAG="--force"
fi

RELIC_SUBJECT_HOME="${{RELIC_SUBJECT_HOME:-$HOME/.relic/subjects/$SUBJECT_ID}}"

"$RELIC_PYTHON" - "$LATEST" "$HERMES_HOME" "$RELIC_SUBJECT_HOME" "$SUBJECT_ID" "${{FORCE_FLAG:-}}" <<'PYEOF'
import sys
sys.path.insert(0, '{relic_root}')
from pathlib import Path
from relic.gumi_plugin.checkin_media_dispatcher import dispatch

llm_output_file = sys.argv[1]
hermes_home = Path(sys.argv[2])
relic_subject_home = Path(sys.argv[3])
subject_id = sys.argv[4]
force = "--force" in sys.argv[5:]

raw = Path(llm_output_file).read_text(encoding="utf-8")
marker = "\\n## Response\\n"
if marker in raw:
    llm_output = raw.split(marker, 1)[1].strip()
else:
    llm_output = raw.strip()
if not llm_output or llm_output == "[SILENT]":
    sys.exit(0)

dispatch(
    llm_output=llm_output,
    hermes_home=hermes_home,
    relic_subject_home=relic_subject_home,
    subject_id=subject_id,
    decision_type="proactivity",
    force=force,
)
PYEOF
'''


def render_memory_sync_script() -> str:
    """Render the memory sync shell script content for gumi_memory_sync cron job."""
    import relic as _relic
    from pathlib import Path as _Path
    relic_root = str(_Path(_relic.__file__).parent.parent)
    return f'''#!/usr/bin/env bash
# Hermes no-agent memory sync script for Relic
# Generated by cron_wiring.py - do not edit manually
#
# Scans session JSONs and syncs outbound messages into MEMORY.md

set -euo pipefail

HERMES_PROFILE_ID="${{RELIC_HERMES_PROFILE_ID:-${{GUMI_HERMES_PROFILE_NAME:-}}}}"
RELIC_PYTHON="${{RELIC_PYTHON:-{sys.executable}}}"

exec "$RELIC_PYTHON" -c "
import sys
sys.path.insert(0, '{relic_root}')
from relic.gumi_plugin.memory_sync import main
main()
" --hermes-home "${{HERMES_HOME:-$HOME/.hermes}}"
'''
