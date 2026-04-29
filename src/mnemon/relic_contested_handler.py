#!/usr/bin/env python3
"""Relic Command Handler — processes /rollback commands from Telegram.

Polls Telegram for messages of the form `/rollback <domain>` in any configured
domain thread. Restores the previous override snapshot for that domain and
notifies the result.

Cron entrypoint: relic:contested-handler   (name kept for compatibility)
Schedule: */5 * * * *
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT = "relic_command_handler"

RELIC_DIR = Path(
    os.environ.get("RELIC_DATA_DIR")
    or str(Path(__file__).resolve().parents[1] / "relic")
)
STATE_FILE = RELIC_DIR / "command_handler_state.json"
DECISIONS_FILE = RELIC_DIR / "reviewer_decisions.jsonl"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

from lib.telegram_notify import send_message

_DOMAIN_ENV = {
    "health":    ("RELIC_HEALTH_TELEGRAM_CHAT_ID",    "RELIC_HEALTH_TELEGRAM_THREAD_ID"),
    "humanness": ("RELIC_HUMANNESS_TELEGRAM_CHAT_ID", "RELIC_HUMANNESS_TELEGRAM_THREAD_ID"),
    "bio":       ("RELIC_CORR_TELEGRAM_CHAT_ID",      "RELIC_CORR_TELEGRAM_THREAD_ID"),
    "inquiry":   ("TELEGRAM_INQUIRY_CHAT_ID",         "TELEGRAM_INQUIRY_THREAD_ID"),
}


def _log(level: str, event: str, **kv: Any) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "script": SCRIPT,
        "event": event,
        **kv,
    }
    print(json.dumps(payload), flush=True)


def _build_thread_map() -> dict[tuple[str, int], str]:
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


def _poll_updates(offset: int) -> list[dict]:
    if not TELEGRAM_BOT_TOKEN:
        return []
    url = (
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
        f"?offset={offset}&timeout=5&allowed_updates%5B%5D=message"
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


def _do_rollback(domain: str) -> str:
    try:
        from mnemon.relic_override_store import list_snapshots, restore_snapshot
        override_file = RELIC_DIR / f"{domain}_overrides.json"
        snaps = list_snapshots(RELIC_DIR, domain)
        if not snaps:
            return f"No snapshots found for {domain} — nothing to roll back."
        latest = snaps[-1]
        restore_snapshot(RELIC_DIR, domain, override_file, timestamp=latest)
        return f"Rolled back {domain} to snapshot {latest}."
    except Exception as exc:
        return f"Rollback failed: {exc}"


def _log_rollback(domain: str, rationale: str, from_user: int | None) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "domain": domain,
        "decision": "rollback",
        "rationale": rationale,
        "source": "human_telegram_rollback",
        "telegram_user_id": from_user,
    }
    RELIC_DIR.mkdir(parents=True, exist_ok=True)
    with open(DECISIONS_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


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
        text = (msg.get("text") or "").strip()
        from_user = msg.get("from", {}).get("id")

        lower = text.lower()
        if not lower.startswith("/rollback"):
            continue

        parts = lower.split()
        if len(parts) >= 2:
            target_domain = parts[1].strip()
        elif thread_id is not None:
            target_domain = thread_map.get((chat_id, int(thread_id)), "")
        else:
            target_domain = ""

        if target_domain not in _DOMAIN_ENV:
            continue

        chat_env, thread_env = _DOMAIN_ENV[target_domain]
        tg_chat = os.environ.get(chat_env, chat_id)
        tg_thread_raw = os.environ.get(thread_env, "")
        tg_thread = int(tg_thread_raw) if tg_thread_raw else thread_id

        rationale = _do_rollback(target_domain)
        _log_rollback(target_domain, rationale, from_user)
        _log("INFO", "rollback_executed", domain=target_domain, result=rationale)
        send_message(
            TELEGRAM_BOT_TOKEN, tg_chat,
            f"<b>[{target_domain.upper()} ROLLBACK]</b> {rationale}",
            thread_id=tg_thread,
        )
        handled += 1

    state["last_update_id"] = new_max_id
    _save_state(state)
    if updates:
        _log("INFO", "poll_done", updates=len(updates), handled=handled,
             next_offset=new_max_id + 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
