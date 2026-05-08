"""Small input helpers shared by subject bootstrap steps."""
from __future__ import annotations

from typing import TextIO


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
    try:
        raw = io_in.readline()
    except (EOFError, OSError):
        raw = ""
    value = raw.strip() if raw else ""
    return value or default or None


def prompt_required(label: str, description: str, io_in: TextIO, io_out: TextIO) -> str:
    while True:
        value = prompt_optional(label, description, io_in, io_out)
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
