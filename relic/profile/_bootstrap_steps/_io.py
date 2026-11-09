"""Small input helpers shared by subject bootstrap steps."""
from __future__ import annotations

from typing import TextIO


def readline_or_none(io_in: TextIO) -> str | None:
    """Read one line; ``None`` means the input is closed (EOF), ``"\\n"`` a blank answer."""
    try:
        raw = io_in.readline()
    except (EOFError, OSError):
        return None
    return raw if raw else None


def require_open_input(raw: str | None, field: str) -> str:
    """Return the line, or raise ``EOFError`` so a required prompt cannot loop forever."""
    if raw is None:
        raise EOFError(f"input closed while waiting for required field: {field}")
    return raw


def prompt_optional(
    label: str,
    description: str,
    io_in: TextIO,
    io_out: TextIO,
    *,
    default: str | None = None,
) -> str | None:
    print(f"\n  {description}", file=io_out)
    hint = f"Enter for {default}" if default is not None else "Enter to skip"
    print(f"  {label} ({hint}): ", end="", flush=True, file=io_out)
    raw = readline_or_none(io_in) or ""
    value = raw.strip()
    return value or default or None


def prompt_required(label: str, description: str, io_in: TextIO, io_out: TextIO) -> str:
    while True:
        print(f"\n  {description}", file=io_out)
        print(f"  {label} (required): ", end="", flush=True, file=io_out)
        value = require_open_input(readline_or_none(io_in), label).strip()
        if value:
            return value
        print("  Required field.", file=io_out)


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def labeled_string(value: str | None, origin: str) -> dict[str, str | None]:
    return {"value": value, "origin": origin}


def labeled_list(values: list[str], origin: str) -> dict[str, object]:
    return {"values": values, "origin": origin}
