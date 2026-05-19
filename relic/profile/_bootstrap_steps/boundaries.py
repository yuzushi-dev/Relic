"""
TUI module for collecting boundaries, opt-out categories, and risk flags of the subject baseline.
"""

from datetime import datetime, timezone
from typing import TextIO
from io import StringIO


def collect_boundaries(io_in: TextIO = None, io_out: TextIO = None) -> dict:
    """
    Collect boundaries, opt-out categories, and risk flags from the subject.

    Args:
        io_in: Input stream (defaults to stdin)
        io_out: Output stream (defaults to stdout)

    Returns:
        dict with keys:
            - "boundaries": dict with "hard_limits", "soft_limits", "negotiable_areas"
            - "opt_out_categories": dict with "values" and "origin"
            - "risk_flags": list of dicts with flag details
    """
    if io_in is None:
        import sys
        io_in = sys.stdin
    if io_out is None:
        import sys
        io_out = sys.stdout

    # Print header
    io_out.write("\n=== Limits, Opt-Out and Risk Flags ===\n\n")
    io_out.flush()

    # Collect boundaries
    io_out.write("BOUNDARIES (comma-separated, skippable)\n")
    io_out.write("-" * 50 + "\n\n")
    io_out.flush()

    hard_limits = _collect_string_array(
        io_in, io_out, "Hard limits (e.g. 'no violence, no drugs')"
    )
    soft_limits = _collect_string_array(
        io_in, io_out, "Soft limits (e.g. 'avoid late night, alcohol in moderation')"
    )
    negotiable_areas = _collect_string_array(
        io_in,
        io_out,
        "Negotiable areas (e.g. 'research methods, contact frequency')",
    )

    boundaries = {
        "hard_limits": {"values": hard_limits, "origin": "subject-stated"},
        "soft_limits": {"values": soft_limits, "origin": "subject-stated"},
        "negotiable_areas": {"values": negotiable_areas, "origin": "subject-stated"},
    }

    # Collect opt-out categories
    io_out.write("\nOPT-OUT CATEGORIES (simple list, skippable)\n")
    io_out.write("-" * 50 + "\n\n")
    io_out.flush()

    opt_out_values = _collect_string_array(
        io_in, io_out, "Opt-out categories (e.g. 'photographs, recordings')"
    )

    opt_out_categories = {"values": opt_out_values, "origin": "subject-stated"}

    # Collect risk flags
    io_out.write("\nRISK FLAGS (loop, skippable)\n")
    io_out.write("-" * 50 + "\n\n")
    io_out.flush()

    risk_flags = _collect_risk_flags(io_in, io_out)

    # Collect escalation contacts
    io_out.write("\nESCALATION CONTACTS (sperimentatore da avvisare in caso di segnali di crisi)\n")
    io_out.write("-" * 50 + "\n\n")
    io_out.flush()

    escalation_contacts = _collect_escalation_contacts(io_in, io_out)

    return {
        "boundaries": boundaries,
        "opt_out_categories": opt_out_categories,
        "risk_flags": risk_flags,
        "escalation_contacts": escalation_contacts,
    }


def _collect_string_array(io_in: TextIO, io_out: TextIO, prompt: str) -> list:
    """
    Collect a comma-separated string array from user input.

    Args:
        io_in: Input stream
        io_out: Output stream
        prompt: Prompt to display

    Returns:
        List of stripped strings, or empty list if input is empty
    """
    io_out.write(f"{prompt}: ")
    io_out.flush()

    line = io_in.readline().strip()

    if not line:
        return []

    # Split by comma and strip whitespace from each element
    values = [item.strip() for item in line.split(",") if item.strip()]
    return values


def _collect_risk_flags(io_in: TextIO, io_out: TextIO) -> list:
    """
    Collect risk flags in a loop.

    Args:
        io_in: Input stream
        io_out: Output stream

    Returns:
        List of risk flag dicts
    """
    risk_flags = []
    flag_num = 1

    while True:
        io_out.write(f"\nAdd a risk flag? (y/n) [default: n]: ")
        io_out.flush()

        response = io_in.readline().strip().lower()

        if not response or response.startswith("n"):
            break

        if not response.startswith("s") and not response.startswith("y"):
            io_out.write("Invalid answer. Enter 'y' for yes or 'n' for no.\n")
            io_out.flush()
            continue

        io_out.write(f"\n--- Risk Flag {flag_num} ---\n")
        io_out.flush()

        # Collect flag_category
        io_out.write("Flag category (e.g. 'self_harm', 'substance_use'): ")
        io_out.flush()
        flag_category = io_in.readline().strip()

        if not flag_category:
            io_out.write("Category required. Operation cancelled.\n")
            io_out.flush()
            continue

        # Collect severity with validation
        severity = _collect_severity(io_in, io_out)

        if severity is None:
            continue

        # Collect notes (optional)
        io_out.write("Notes (optional, press Enter to skip): ")
        io_out.flush()
        notes = io_in.readline().strip()

        # Create risk flag with auto-generated reviewed_at
        reviewed_at = datetime.now(timezone.utc).isoformat()

        risk_flag = {
            "flag_category": flag_category,
            "severity": severity,
            "notes": notes if notes else None,
            "reviewed_at": reviewed_at,
            "origin": "researcher-coded",
        }

        risk_flags.append(risk_flag)
        flag_num += 1

    return risk_flags


def _collect_escalation_contacts(io_in: TextIO, io_out: TextIO) -> list:
    """Collect researcher/experimenter escalation contacts (loop, skippable)."""
    contacts = []
    contact_num = 1

    while True:
        io_out.write(f"Add escalation contact? (y/n) [default: n]: ")
        io_out.flush()
        response = io_in.readline().strip().lower()

        if not response or response.startswith("n"):
            break
        if not response.startswith("y"):
            io_out.write("Enter 'y' or 'n'.\n")
            io_out.flush()
            continue

        io_out.write(f"\n--- Escalation Contact {contact_num} ---\n")
        io_out.flush()

        io_out.write("Name (e.g. 'Dr. Rossi'): ")
        io_out.flush()
        name = io_in.readline().strip()
        if not name:
            io_out.write("Name required. Skipping.\n")
            io_out.flush()
            continue

        io_out.write("Email address for safety alerts: ")
        io_out.flush()
        email_value = io_in.readline().strip()

        io_out.write("Telegram chat id or @username for safety alerts: ")
        io_out.flush()
        telegram_value = io_in.readline().strip()
        if not email_value or not telegram_value:
            io_out.write("Both email and Telegram are required. Skipping.\n")
            io_out.flush()
            continue

        valid_signals = ["crisis_language", "self_harm_language", "dependency_escalation", "all"]
        io_out.write(f"Notify on signals ({', '.join(valid_signals)}) [default: all]: ")
        io_out.flush()
        signals_raw = io_in.readline().strip().lower() or "all"
        notify_on = [s.strip() for s in signals_raw.split(",") if s.strip() in valid_signals]
        if not notify_on:
            notify_on = ["all"]

        contacts.extend([
            {
                "name": name,
                "method": "email",
                "value": email_value,
                "notify_on": notify_on,
            },
            {
                "name": name,
                "method": "telegram",
                "value": telegram_value,
                "notify_on": notify_on,
            },
        ])
        contact_num += 1

    return contacts


def _collect_severity(io_in: TextIO, io_out: TextIO) -> str:
    """
    Collect severity level with validation.

    Args:
        io_in: Input stream
        io_out: Output stream

    Returns:
        Valid severity string or None if collection failed
    """
    valid_severities = ["low", "medium", "high", "critical"]

    while True:
        io_out.write(
            f"Severity ({' | '.join(valid_severities)}): "
        )
        io_out.flush()

        severity = io_in.readline().strip().lower()

        if severity in valid_severities:
            return severity

        io_out.write(
            f"Invalid value. Choose one of: {', '.join(valid_severities)}\n"
        )
        io_out.flush()
