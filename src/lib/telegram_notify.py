"""Shared Telegram notification helpers for Relic analyst modules.

Provides send_message() and send_contested_keyboard() used by analyst modules
to deliver CONTESTED alerts with inline A/B/C buttons.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from lib.log import warn

_API = "https://api.telegram.org/bot{token}/{method}"


def _post(token: str, method: str, payload: dict[str, Any]) -> dict | None:
    url = _API.format(token=token, method=method)
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        warn("telegram_notify", method, code=e.code, body=e.read().decode()[:200])
    except Exception as exc:
        warn("telegram_notify", method, error=str(exc))
    return None


def send_message(
    token: str,
    chat_id: str,
    text: str,
    thread_id: int | None = None,
    parse_mode: str = "HTML",
) -> dict | None:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if thread_id is not None:
        payload["message_thread_id"] = thread_id
    return _post(token, "sendMessage", payload)


def send_contested_keyboard(
    token: str,
    chat_id: str,
    thread_id: int | None,
    domain: str,
    header: str,
    options: dict[str, str],
) -> dict | None:
    """Send a CONTESTED alert with A/B/C inline keyboard buttons.

    Args:
        token: Telegram bot token.
        chat_id: Target chat ID.
        thread_id: Topic/thread ID (None for general chat).
        domain: Domain key used as prefix in callback_data (e.g. "health").
        header: Short summary shown above the buttons.
        options: {"a": "Apply critical override", "b": "Monitor", "c": "Apply degraded"}
    """
    text = f"<b>[{domain.upper()} CONTESTED]</b>\n{header}"
    buttons = [
        [
            {"text": f"{k.upper()} — {v}", "callback_data": f"{domain}:{k}"}
            for k, v in sorted(options.items())
        ]
    ]
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {"inline_keyboard": buttons},
    }
    if thread_id is not None:
        payload["message_thread_id"] = thread_id
    return _post(token, "sendMessage", payload)


def answer_callback_query(token: str, callback_query_id: str, text: str = "") -> None:
    _post(token, "answerCallbackQuery", {
        "callback_query_id": callback_query_id,
        "text": text,
        "show_alert": False,
    })


def send_action_notification(
    token: str,
    chat_id: str,
    thread_id: int | None,
    domain: str,
    action: str,
    verdict: str,
    confidence: float,
    details: list[str],
    llm_available: bool = True,
) -> dict | None:
    """Notify that an override was auto-applied (or not) by the autonomous pipeline."""
    status_line = {
        "critical":  "Applied CRITICAL override",
        "degraded":  "Applied DEGRADED override",
        "clear":     "Cleared override (returning to defaults)",
        "monitor":   "Monitoring — no override applied",
    }.get(action, f"Action: {action}")

    llm_note = "" if llm_available else "\n⚠️ Judge LLM unavailable — heuristic applied"
    details_str = "\n".join(f"  · {d}" for d in details)

    text = (
        f"<b>[{domain.upper()}]</b> {status_line}\n"
        f"Judge: <code>{verdict}</code> (confidence: {confidence:.2f}){llm_note}\n"
        f"{details_str}\n"
        f"\n<i>Rollback: python3 -m relic.override_manager rollback {domain}</i>"
    )
    return send_message(token, chat_id, text, thread_id=thread_id)
