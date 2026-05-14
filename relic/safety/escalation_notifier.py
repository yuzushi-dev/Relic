"""Escalation notifier: alerts researcher contacts when safety signals are detected.

Notification paths:
- JSONL audit log at ~/.relic/subjects/{subject_id}/escalation_log.jsonl (always)
- Email via smtplib if contact method == "email" and RELIC_SMTP_* env vars set
- Stderr warning if no transport available (visible in cron logs)

Privacy constraints:
- Never logs raw user message text — only signal_type + subject_id + timestamp
- Contact values are read from delivery_policy.json (researcher-only access)
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_escalation_contacts(subject_id: str) -> list[dict[str, Any]]:
    """Load escalation_contacts from delivery_policy.json. Returns [] on error."""
    try:
        from relic.profile.registry import ProfileRegistry
        registry = ProfileRegistry()
        policy_path = registry._delivery_policy_path(subject_id)
        if not policy_path.exists():
            return []
        with open(policy_path, encoding="utf-8") as fh:
            policy = json.load(fh)
        return policy.get("escalation_contacts", [])
    except Exception as exc:
        logger.warning("_load_escalation_contacts failed for %s: %s", subject_id, exc)
        return []


def _should_notify(contact: dict[str, Any], signal_type: str) -> bool:
    """Return True if contact should be notified for this signal."""
    notify_on = contact.get("notify_on", ["all"])
    return "all" in notify_on or signal_type in notify_on


def _write_audit_log(subject_id: str, signal_type: str, contact_name: str, method: str) -> None:
    log_path = Path(f"~/.relic/subjects/{subject_id}/escalation_log.jsonl").expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": _now_iso(),
        "subject_id": subject_id,
        "signal_type": signal_type,
        "notified_contact": contact_name,
        "method": method,
    }
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def _send_email(to_address: str, subject_id: str, signal_type: str) -> bool:
    """Send email alert via RELIC_SMTP_* env vars. Returns True on success."""
    smtp_host = os.environ.get("RELIC_SMTP_HOST", "")
    smtp_port = int(os.environ.get("RELIC_SMTP_PORT", "587"))
    smtp_user = os.environ.get("RELIC_SMTP_USER", "")
    smtp_pass = os.environ.get("RELIC_SMTP_PASS", "")
    smtp_from = os.environ.get("RELIC_SMTP_FROM", smtp_user)

    if not smtp_host or not smtp_user:
        return False

    try:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["Subject"] = f"[Relic Safety Alert] {signal_type} — subject {subject_id}"
        msg["From"] = smtp_from
        msg["To"] = to_address
        msg.set_content(
            f"Relic safety signal detected.\n\n"
            f"Subject ID: {subject_id}\n"
            f"Signal type: {signal_type}\n"
            f"Timestamp: {_now_iso()}\n\n"
            f"Please review the subject's session logs and intervene if necessary.\n"
            f"This message was generated automatically by the Relic safety pipeline."
        )
        with smtplib.SMTP(smtp_host, smtp_port) as smtp:
            smtp.starttls()
            smtp.login(smtp_user, smtp_pass)
            smtp.send_message(msg)
        return True
    except Exception as exc:
        logger.warning("Email escalation failed to %s: %s", to_address, exc)
        return False


def notify_escalation(subject_id: str, signal_type: str) -> list[dict[str, Any]]:
    """Notify all matching escalation contacts for subject_id + signal_type.

    Always writes audit log. Attempts email delivery if configured.

    Returns list of notification results (one per contact attempted).
    """
    contacts = _load_escalation_contacts(subject_id)
    results = []

    if not contacts:
        logger.warning(
            "Escalation signal '%s' for subject '%s' — no escalation contacts configured.",
            signal_type, subject_id,
        )
        return results

    for contact in contacts:
        if not _should_notify(contact, signal_type):
            continue

        name = contact.get("name", "unknown")
        method = contact.get("method", "email")
        value = contact.get("value", "")

        _write_audit_log(subject_id, signal_type, name, method)

        delivered = False
        if method == "email" and value:
            delivered = _send_email(value, subject_id, signal_type)

        if not delivered:
            # Fallback: write to stderr so cron logs capture it
            import sys
            print(
                f"[RELIC ESCALATION] subject={subject_id} signal={signal_type} "
                f"contact={name} method={method} — no transport (check RELIC_SMTP_* env vars)",
                file=sys.stderr,
            )

        results.append({
            "contact_name": name,
            "method": method,
            "delivered": delivered,
            "signal_type": signal_type,
        })

    return results
