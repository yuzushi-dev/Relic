"""Escalation notifier: alerts researcher contacts when safety signals are detected.

Notification paths:
- JSONL audit log at ~/.relic/subjects/{subject_id}/escalation_log.jsonl (always)
- Email via smtplib if contact method == "email" and RELIC_SMTP_* env vars set
- Telegram via Bot API if contact method == "telegram" and RELIC_TELEGRAM_BOT_TOKEN is set
- Stderr warning if no transport available (visible in cron logs)

Privacy constraints:
- Never logs raw user message text — only signal_type + subject_id + timestamp
- Contact values are read from delivery_policy.json (researcher-only access)
"""
from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
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
        if policy_path.exists():
            with open(policy_path, encoding="utf-8") as fh:
                policy = json.load(fh)
            contacts = policy.get("escalation_contacts", [])
            if contacts:
                return contacts

        baseline_path = policy_path.parent / "baseline_user_profile.json"
        if baseline_path.exists():
            with open(baseline_path, encoding="utf-8") as fh:
                baseline = json.load(fh)
            return baseline.get("escalation_contacts", [])
        return []
    except Exception as exc:
        logger.warning("_load_escalation_contacts failed for %s: %s", subject_id, exc)
        return []


def _should_notify(contact: dict[str, Any], signal_type: str) -> bool:
    """Return True if contact should be notified for this signal."""
    notify_on = contact.get("notify_on", ["all"])
    return "all" in notify_on or signal_type in notify_on


def _escalation_audit_path(subject_id: str) -> Path:
    return Path(f"~/.relic/subjects/{subject_id}/escalation_log.jsonl").expanduser()


def _write_audit_log(
    subject_id: str,
    signal_type: str,
    contact_name: str,
    method: str,
    *,
    delivery_status: str | None = None,
    evidence_refs: list[str] | None = None,
    warning_tier: str | None = None,
    confidence: float | None = None,
) -> None:
    log_path = _escalation_audit_path(subject_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": _now_iso(),
        "subject_id": subject_id,
        "signal_type": signal_type,
        "notified_contact": contact_name,
        "method": method,
    }
    if delivery_status is not None:
        entry["delivery_status"] = delivery_status
    if evidence_refs is not None:
        entry["evidence_refs"] = evidence_refs
    if warning_tier is not None:
        entry["warning_tier"] = warning_tier
    if confidence is not None:
        entry["confidence"] = confidence
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def _write_audit_log_safely(*args, **kwargs) -> None:
    """Write audit log without blocking notification flow on I/O errors."""
    try:
        _write_audit_log(*args, **kwargs)
    except Exception as exc:
        logger.warning("Escalation audit write failed: %s", exc)


def _send_email(
    to_address: str,
    subject_id: str,
    signal_type: str,
    *,
    evidence_refs: list[str] | None = None,
    warning_tier: str | None = None,
    confidence: float | None = None,
) -> bool:
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
        metadata_lines = []
        if warning_tier is not None:
            metadata_lines.append(f"Warning tier: {warning_tier}")
        if confidence is not None:
            metadata_lines.append(f"Confidence: {confidence}")
        if evidence_refs is not None:
            metadata_lines.append(f"Evidence refs: {', '.join(evidence_refs)}")
        metadata = "\n".join(metadata_lines)
        if metadata:
            metadata = metadata + "\n\n"
        msg.set_content(
            f"Relic safety signal detected.\n\n"
            f"Subject ID: {subject_id}\n"
            f"Signal type: {signal_type}\n"
            f"Timestamp: {_now_iso()}\n\n"
            f"{metadata}"
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


def _telegram_token() -> str:
    token_env = os.environ.get("RELIC_TELEGRAM_BOT_TOKEN_ENV", "")
    if token_env:
        token = os.environ.get(token_env, "")
        if token:
            return token
    return os.environ.get("RELIC_TELEGRAM_BOT_TOKEN", "") or os.environ.get("TELEGRAM_BOT_TOKEN", "")


def _normalize_telegram_chat_id(value: str) -> str:
    if value.startswith("telegram:"):
        return value.removeprefix("telegram:")
    return value


def _notification_text(
    subject_id: str,
    signal_type: str,
    *,
    evidence_refs: list[str] | None = None,
    warning_tier: str | None = None,
    confidence: float | None = None,
) -> str:
    metadata_lines = []
    if warning_tier is not None:
        metadata_lines.append(f"Warning tier: {warning_tier}")
    if confidence is not None:
        metadata_lines.append(f"Confidence: {confidence}")
    if evidence_refs is not None:
        metadata_lines.append(f"Evidence refs: {', '.join(evidence_refs)}")
    metadata = "\n".join(metadata_lines)
    if metadata:
        metadata = metadata + "\n\n"
    return (
        "Relic safety signal detected.\n\n"
        f"Subject ID: {subject_id}\n"
        f"Signal type: {signal_type}\n"
        f"Timestamp: {_now_iso()}\n\n"
        f"{metadata}"
        "Please review the subject's session logs and intervene if necessary.\n"
        "This message was generated automatically by the Relic safety pipeline."
    )


def _send_telegram_message(
    chat_id: str,
    subject_id: str,
    signal_type: str,
    *,
    evidence_refs: list[str] | None = None,
    warning_tier: str | None = None,
    confidence: float | None = None,
) -> bool:
    """Send a redacted Telegram alert via Bot API. Returns True on success."""
    token = _telegram_token()
    if not token or not chat_id:
        return False

    normalized_chat_id = _normalize_telegram_chat_id(chat_id)
    text = _notification_text(
        subject_id,
        signal_type,
        evidence_refs=evidence_refs,
        warning_tier=warning_tier,
        confidence=confidence,
    )
    data = urllib.parse.urlencode({"chat_id": normalized_chat_id, "text": text}).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read()
        payload = json.loads(body.decode("utf-8") or "{}")
        return payload.get("ok") is True
    except Exception as exc:
        logger.warning("Telegram escalation failed to %s: %s", chat_id, exc)
        return False


def notify_escalation(
    subject_id: str,
    signal_type: str,
    *,
    evidence_refs: list[str] | None = None,
    warning_tier: str | None = None,
    confidence: float | None = None,
) -> list[dict[str, Any]]:
    """Notify all matching escalation contacts for subject_id + signal_type.

    Always writes audit log. Attempts email and Telegram delivery if configured.

    Returns list of notification results (one per contact attempted).
    """
    contacts = _load_escalation_contacts(subject_id)
    results = []

    if not contacts:
        audit_kwargs = {"delivery_status": "no_contacts"}
        if evidence_refs is not None:
            audit_kwargs["evidence_refs"] = evidence_refs
        if warning_tier is not None:
            audit_kwargs["warning_tier"] = warning_tier
        if confidence is not None:
            audit_kwargs["confidence"] = confidence
        _write_audit_log_safely(subject_id, signal_type, "none", "none", **audit_kwargs)
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

        audit_kwargs = {}
        if evidence_refs is not None:
            audit_kwargs["evidence_refs"] = evidence_refs
        if warning_tier is not None:
            audit_kwargs["warning_tier"] = warning_tier
        if confidence is not None:
            audit_kwargs["confidence"] = confidence
        if audit_kwargs:
            _write_audit_log_safely(subject_id, signal_type, name, method, **audit_kwargs)
        else:
            _write_audit_log_safely(subject_id, signal_type, name, method)

        delivered = False
        if method == "email" and value:
            delivered = _send_email(
                value,
                subject_id,
                signal_type,
                evidence_refs=evidence_refs,
                warning_tier=warning_tier,
                confidence=confidence,
            )
        elif method == "telegram" and value:
            delivered = _send_telegram_message(
                value,
                subject_id,
                signal_type,
                evidence_refs=evidence_refs,
                warning_tier=warning_tier,
                confidence=confidence,
            )

        if not delivered:
            # Fallback: write to stderr so cron logs capture it
            import sys
            hint = (
                "check RELIC_SMTP_* env vars"
                if method == "email"
                else "check RELIC_TELEGRAM_BOT_TOKEN or RELIC_TELEGRAM_BOT_TOKEN_ENV"
            )
            print(
                f"[RELIC ESCALATION] subject={subject_id} signal={signal_type} "
                f"contact={name} method={method} — no transport ({hint})",
                file=sys.stderr,
            )

        results.append({
            "contact_name": name,
            "method": method,
            "delivered": delivered,
            "signal_type": signal_type,
        })

    return results
