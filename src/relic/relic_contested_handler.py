#!/usr/bin/env python3
"""Relic Contested Handler — processes human A/B/C responses to CONTESTED alerts.

Polls Telegram for new messages in each domain's alert thread.
When A/B/C is found after a pending CONTESTED alert, applies the corresponding
override action and logs to reviewer_decisions.jsonl.

Cron entrypoint: relic:contested-handler
Schedule: */5 * * * *  (every 5 minutes)
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT = "relic_contested_handler"

RELIC_DIR = Path(
    os.environ.get("RELIC_DATA_DIR")
    or str(Path(__file__).resolve().parents[1] / "relic")
)
STATE_FILE = RELIC_DIR / "contested_handler_state.json"
DECISIONS_FILE = RELIC_DIR / "reviewer_decisions.jsonl"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Map env var prefix → domain name
_DOMAIN_ENV = {
    "health":    ("RELIC_HEALTH_TELEGRAM_CHAT_ID",    "RELIC_HEALTH_TELEGRAM_THREAD_ID"),
    "humanness": ("RELIC_HUMANNESS_TELEGRAM_CHAT_ID", "RELIC_HUMANNESS_TELEGRAM_THREAD_ID"),
    "bio":       ("RELIC_CORR_TELEGRAM_CHAT_ID",      "RELIC_CORR_TELEGRAM_THREAD_ID"),
    "inquiry":   ("TELEGRAM_INQUIRY_CHAT_ID",         "TELEGRAM_INQUIRY_THREAD_ID"),
}


# ── Logging ───────────────────────────────────────────────────────────────────

def _log(level: str, event: str, **kv: Any) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "script": SCRIPT,
        "event": event,
        **kv,
    }
    print(json.dumps(payload), flush=True)


# ── Thread → domain routing ───────────────────────────────────────────────────

def _build_thread_map() -> dict[tuple[str, int], str]:
    """Returns {(chat_id_str, thread_id_int): domain} from env vars."""
    mapping: dict[tuple[str, int], str] = {}
    for domain, (chat_env, thread_env) in _DOMAIN_ENV.items():
        chat_id = os.environ.get(chat_env, "").strip()
        thread_id = os.environ.get(thread_env, "").strip()
        if chat_id and thread_id:
            try:
                mapping[(chat_id, int(thread_id))] = domain
            except ValueError:
                pass
    return mapping


# ── State persistence ─────────────────────────────────────────────────────────

def _load_state() -> dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"last_update_id": 0}


def _save_state(state: dict[str, Any]) -> None:
    RELIC_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ── Telegram polling ──────────────────────────────────────────────────────────

def _poll_updates(offset: int) -> list[dict]:
    if not TELEGRAM_BOT_TOKEN:
        return []
    url = (
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        f"?offset={offset}&timeout=5&allowed_updates=message"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
            return data.get("result", [])
    except urllib.error.HTTPError as e:
        _log("WARN", "telegram_poll_error", code=e.code, body=e.read().decode()[:200])
    except Exception as exc:
        _log("WARN", "telegram_poll_error", error=str(exc))
    return []


# ── Action dispatch ───────────────────────────────────────────────────────────

def _apply_health_action(option: str) -> str:
    """Apply override for health domain. Returns rationale string."""
    last_run_path = RELIC_DIR / "last_health_run.json"
    if not last_run_path.exists():
        return "last_health_run.json not found — cannot apply override; monitor only"

    try:
        last_run = json.loads(last_run_path.read_text())
    except Exception:
        return "failed to read last_health_run.json — monitor only"

    metrics = last_run.get("metrics", {})
    neglected = last_run.get("neglected", [])

    if option == "b":
        return "option B selected: monitor without override"

    severity = "critical" if option == "a" else "degraded"
    try:
        from relic.relic_health_monitor import apply_remediation
        apply_remediation(metrics, neglected, severity)
        return f"option {option.upper()} applied: {severity} override written"
    except Exception as exc:
        return f"apply_remediation failed: {exc}"


def _apply_humanness_action(option: str) -> str:
    if option == "b":
        return "option B selected: monitor without override"
    severity = "critical" if option == "a" else "degraded"
    try:
        from relic.relic_humanness_analyst import apply_remediation
        # Humanness needs metrics — try to load last run
        last_run_path = RELIC_DIR / "last_humanness_run.json"
        if last_run_path.exists():
            last_run = json.loads(last_run_path.read_text())
            apply_remediation(last_run.get("metrics", {}), severity)
        else:
            return "last_humanness_run.json not found — monitor only"
        return f"option {option.upper()} applied: {severity} override written"
    except Exception as exc:
        return f"apply_remediation failed: {exc}"


_ACTION_DISPATCH: dict[str, Any] = {
    "health":    _apply_health_action,
    "humanness": _apply_humanness_action,
    "bio":       lambda opt: f"bio CONTESTED option {opt.upper()} acknowledged — manual review required",
    "inquiry":   lambda opt: f"inquiry CONTESTED option {opt.upper()} acknowledged — manual review required",
}


# ── Audit trail ───────────────────────────────────────────────────────────────

def _log_decision(domain: str, option: str, rationale: str, from_user: int | None) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "domain": domain,
        "decision": {"a": "apply_critical", "b": "monitor", "c": "apply_degraded"}.get(option, option),
        "rationale": rationale,
        "source": f"human_telegram_{option}",
        "telegram_user_id": from_user,
    }
    RELIC_DIR.mkdir(parents=True, exist_ok=True)
    with open(DECISIONS_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    _log("INFO", "decision_logged", domain=domain, decision=entry["decision"])


# ── Main loop ─────────────────────────────────────────────────────────────────

def main() -> int:
    if not TELEGRAM_BOT_TOKEN:
        _log("WARN", "skip", reason="TELEGRAM_BOT_TOKEN not set")
        return 1

    thread_map = _build_thread_map()
    if not thread_map:
        _log("WARN", "skip", reason="no domain thread IDs configured in env")
        return 1

    state = _load_state()
    offset = state.get("last_update_id", 0) + 1

    updates = _poll_updates(offset)
    if not updates:
        _log("INFO", "no_updates", offset=offset)
        return 0

    new_max_id = offset - 1
    handled = 0

    for update in updates:
        update_id = update.get("update_id", 0)
        if update_id > new_max_id:
            new_max_id = update_id

        msg = update.get("message", {})
        if not msg:
            continue

        chat_id = str(msg.get("chat", {}).get("id", ""))
        thread_id = msg.get("message_thread_id")
        text = (msg.get("text") or "").strip().lower()
        from_user = msg.get("from", {}).get("id")

        if text not in ("a", "b", "c"):
            continue

        if thread_id is None:
            continue

        domain = thread_map.get((chat_id, int(thread_id)))
        if domain is None:
            continue

        dispatch = _ACTION_DISPATCH.get(domain)
        if dispatch is None:
            continue

        rationale = dispatch(text)
        _log_decision(domain, text, rationale, from_user)
        _log("INFO", "contested_resolved",
             domain=domain, option=text.upper(), rationale=rationale)
        handled += 1

    state["last_update_id"] = new_max_id
    _save_state(state)
    _log("INFO", "poll_done", updates=len(updates), handled=handled,
         next_offset=new_max_id + 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
