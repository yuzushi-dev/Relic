"""TUI step: researcher controls for first-contact messages."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import TextIO


_ACTIONS = {
    "1": "preview",
    "2": "regenerate",
    "3": "edit",
    "4": "block",
    "5": "dry_run",
    "6": "send",
    "preview": "preview",
    "regenerate": "regenerate",
    "edit": "edit",
    "block": "block",
    "dry-run": "dry_run",
    "dry_run": "dry_run",
    "send": "send",
}


def run_first_contact_controls(io_in: TextIO, io_out: TextIO, ctx: dict) -> dict:
    """Run researcher controls for the composed first-contact message."""
    profile_dir = Path(ctx["profile_dir"])
    delivery_enabled = bool(ctx.get("delivery_config", {}).get("delivery_enabled"))
    message_text = str(ctx.get("message_text", ""))
    while True:
        print("\n--- First Contact Controls ---", file=io_out)
        print("1) preview", file=io_out)
        print("2) regenerate", file=io_out)
        print("3) edit", file=io_out)
        print("4) block", file=io_out)
        print("5) dry-run", file=io_out)
        print("6) send", file=io_out)
        raw = io_in.readline()
        action = _ACTIONS.get(raw.strip().lower() if raw else "preview")
        if not action:
            print("Invalid choice.", file=io_out)
            continue
        if action in {"send", "dry_run"} and not delivery_enabled:
            print("Delivery not enabled: choose preview, edit, regenerate, or block.", file=io_out)
            continue
        if action == "preview":
            print("\n--- Preview Intro ---", file=io_out)
            print(message_text, file=io_out)
            return {"action": action, "payload": {"message_text": message_text}}
        if action == "block":
            print("Block reason:", file=io_out)
            reason_raw = io_in.readline()
            reason = reason_raw.strip() if reason_raw else "blocked by researcher"
            payload = {"reason": reason, "message_text_hash_only": True}
            (profile_dir / "intro_blocked.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            return {"action": action, "payload": payload}
        if action == "edit":
            editor = os.environ.get("EDITOR")
            edited = message_text
            if editor:
                with tempfile.NamedTemporaryFile("w+", encoding="utf-8", suffix=".txt") as fh:
                    fh.write(message_text)
                    fh.flush()
                    os.system(f"{editor} {fh.name}")
                    fh.seek(0)
                    edited = fh.read().strip()
            else:
                print("EDITOR not set; paste edited text, empty line to keep preview.", file=io_out)
                raw_edit = io_in.readline()
                edited = raw_edit.strip() or message_text
            return {"action": action, "payload": {"message_text": edited, "origin": "manually-edited"}}
        return {"action": action, "payload": {"dry_run": action == "dry_run"}}
