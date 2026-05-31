"""
gumi_memory_sync — auto-update MEMORY.md with cron-delivered outbound messages.

Runs as a no-agent Hermes cron job offset from the checkin_message job.
Scans new session JSONs, extracts assistant messages, and appends a bounded
rolling block to MEMORY.md under HTML comment markers.

Idempotent via watermark file:
  <hermes_home>/state/memory_sync_watermark.json
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# Max entries kept in the rolling block
_MAX_ENTRIES = 20

# Block markers
_BLOCK_BEGIN = "<!-- gumi:memory_sync:begin -->"
_BLOCK_END = "<!-- gumi:memory_sync:end -->"


# ---------------------------------------------------------------------------
# Watermark
# ---------------------------------------------------------------------------

def _default_watermark() -> dict[str, Any]:
    return {"last_session_mtime_ns": 0, "last_message_idx_per_session": {}}


def _read_watermark(state_dir: Path) -> dict[str, Any]:
    path = state_dir / "memory_sync_watermark.json"
    if not path.exists():
        return _default_watermark()
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return _default_watermark()


def _write_watermark(state_dir: Path, watermark: dict[str, Any]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    tmp = state_dir / "memory_sync_watermark.json.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(watermark, f, ensure_ascii=False)
    os.replace(tmp, state_dir / "memory_sync_watermark.json")


# ---------------------------------------------------------------------------
# Session scanning
# ---------------------------------------------------------------------------

def _delivery_enabled(hermes_home: Path) -> bool:
    """Check if delivery is enabled for this subject.

    Looks for delivery_enabled flag in relationship_policy.md.
    Returns True by default (safe — missing flag means delivery is allowed).
    """
    try:
        policy_path = hermes_home / "workspace" / "gumi" / "relationship_policy.md"
        if not policy_path.exists():
            return True
        text = policy_path.read_text(encoding="utf-8")
        # Case-insensitive scan for "delivery_enabled: false"
        return "delivery_enabled: false" not in text.lower()
    except Exception:
        return True


def _parse_session_filename(name: str) -> tuple[str, str] | None:
    """Extract session_id and job_id from session_cron_<jobid>_<ts>.json."""
    m = re.match(r"session_cron_(.+)_\d+\.json", name)
    if m:
        return name, m.group(1)
    return None


def _extract_outbound_entries(
    session_path: Path,
    session_id: str,
    job_id: str,
    start_idx: int,
) -> list[dict[str, Any]]:
    """Extract assistant messages from a session JSON that are valid outbound deliveries."""
    try:
        with open(session_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    # Skip internal maintenance cron jobs (workspace compaction, continuity
    # review): their assistant output is an audit report read via workspace
    # tools, NOT a message delivered to the subject. Counting them polluted
    # MEMORY.md — the only interactive-continuity bridge — with tooling chatter.
    # Fail-open: if the helper is unavailable, fall back to the legacy behaviour.
    try:
        from relic.hermes_plugin.recent_outbound import is_maintenance_session
        if is_maintenance_session(data):
            return []
    except Exception:
        pass

    messages = data.get("messages", [])
    entries: list[dict[str, Any]] = []

    for msg in messages[start_idx:]:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content") or ""
        if not content or content == "[SILENT]":
            continue

        # Skip if result/delivery_status field indicates error
        result = msg.get("result") or {}
        delivery_status = result.get("delivery_status") if isinstance(result, dict) else None
        if delivery_status == "error":
            continue

        # Extract timestamp — prefer session metadata, then message ts, then file mtime
        ts = msg.get("ts") or msg.get("timestamp") or session_path.stat().st_mtime
        entries.append({
            "session_id": session_id,
            "job_id": job_id,
            "ts": ts,
            "text": content,
        })

    return entries


def _scan_sessions(
    hermes_home: Path,
    watermark: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Scan all cron sessions newer than the watermark and collect outbound entries.

    Returns (entries, updated_last_mtime) where updated_last_mtime is the max
    mtime_ns across all scanned sessions.
    """
    sessions_dir = hermes_home / "sessions"
    if not sessions_dir.is_dir():
        return [], 0

    all_entries: list[dict[str, Any]] = []
    updated_last_mtime = watermark.get("last_session_mtime_ns", 0)
    last_idx_per_session = watermark.get("last_message_idx_per_session", {})

    # Sort by mtime ascending (process oldest first)
    session_files = sorted(
        sessions_dir.glob("session_cron_*.json"),
        key=lambda p: p.stat().st_mtime_ns,
    )

    for session_path in session_files:
        parsed = _parse_session_filename(session_path.name)
        if parsed is None:
            continue

        session_id, job_id = parsed
        mtime_ns = session_path.stat().st_mtime_ns

        # Skip sessions older than watermark
        if mtime_ns <= watermark.get("last_session_mtime_ns", 0):
            continue

        start_idx = last_idx_per_session.get(session_id, 0)

        # Count messages first to know where to resume next time
        try:
            with open(session_path, encoding="utf-8") as f:
                data = json.load(f)
            msg_count = len(data.get("messages", []))
        except Exception:
            msg_count = start_idx  # Can't read — don't advance

        entries = _extract_outbound_entries(session_path, session_id, job_id, start_idx)
        all_entries.extend(entries)

        # Update watermark for this session
        if msg_count > start_idx:
            last_idx_per_session[session_id] = msg_count

        if mtime_ns > updated_last_mtime:
            updated_last_mtime = mtime_ns

    # Persist updated last_idx_per_session even if no entries found
    watermark["last_message_idx_per_session"] = last_idx_per_session

    return all_entries, updated_last_mtime


# ---------------------------------------------------------------------------
# MEMORY.md block management
# ---------------------------------------------------------------------------

def _render_entry(entry: dict[str, Any]) -> str:
    ts = entry["ts"]
    if isinstance(ts, (int, float)):
        import time

        ts_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
    else:
        ts_str = str(ts)
    job_id = entry.get("job_id", "unknown")
    text = entry["text"]
    quoted = "\n> ".join(text.strip().splitlines())
    return f"### {ts_str} (job={job_id})\n> {quoted}\n"


def _read_existing_entries(memory_path: Path) -> list[dict[str, Any]]:
    """Read existing sync block entries from MEMORY.md to preserve ordering."""
    if not memory_path.exists():
        return []
    text = memory_path.read_text(encoding="utf-8")
    begin = text.find(_BLOCK_BEGIN)
    end = text.find(_BLOCK_END)
    if begin == -1 or end == -1:
        return []
    block = text[begin + len(_BLOCK_BEGIN):end]
    entries: list[dict[str, Any]] = []
    # Parse ### TS (job=ID)\n> text lines
    heading_re = re.compile(r"^### (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) \(job=(.+?)\)$", re.MULTILINE)
    current: dict[str, Any] | None = None
    quote_lines: list[str] = []
    for line in block.splitlines():
        hm = heading_re.match(line.strip())
        if hm:
            if current:
                current["text"] = "\n".join(quote_lines).strip()
                entries.append(current)
                quote_lines = []
            ts_str, job_id = hm.group(1), hm.group(2)
            import time

            ts = time.mktime(time.strptime(ts_str, "%Y-%m-%d %H:%M"))
            current = {"session_id": "", "job_id": job_id, "ts": ts, "text": ""}
        elif line.strip().startswith("> ") and current is not None:
            quote_lines.append(line.strip()[2:])
    if current:
        current["text"] = "\n".join(quote_lines).strip()
        entries.append(current)
    return entries


def _build_block(entries: list[dict[str, Any]]) -> str:
    """Build the bounded HTML block from a list of entries (newest last)."""
    lines = [f"\n{_BLOCK_BEGIN}\n"]
    for entry in entries:
        lines.append(_render_entry(entry))
    lines.append(f"{_BLOCK_END}\n")
    return "".join(lines)


def _rewrite_memory_block(memory_path: Path, new_entries: list[dict[str, Any]]) -> bool:
    """Rewrite the bounded block in MEMORY.md, merging prior + new entries."""
    prior = _read_existing_entries(memory_path)
    merged = prior + new_entries
    # Keep most recent _MAX_ENTRIES
    merged = merged[-_MAX_ENTRIES:]
    block = _build_block(merged)

    text = memory_path.read_text(encoding="utf-8")
    begin = text.find(_BLOCK_BEGIN)
    end = text.find(_BLOCK_END)

    if begin != -1 and end != -1:
        # Replace existing block
        text = text[:begin] + block + text[end + len(_BLOCK_END):]
    elif begin == -1 and end == -1:
        # Append block at end
        text = text.rstrip() + block
    else:
        # Malformed — log and skip
        return False

    tmp = memory_path.with_suffix(".md.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, memory_path)
    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sync(hermes_home: Path) -> dict[str, Any]:
    """Sync cron-delivered messages into MEMORY.md.

    Returns a summary dict with keys: scanned, appended, skipped, errors, done.
    """
    result: dict[str, Any] = {"scanned": 0, "appended": 0, "skipped": 0, "errors": 0, "done": False}

    if not hermes_home.is_dir():
        result["skipped"] = "no_hermes_home"
        return result

    memory_path = hermes_home / "MEMORY.md"
    if not memory_path.exists():
        result["skipped"] = "no_memory"
        return result

    if not _delivery_enabled(hermes_home):
        result["skipped"] = "delivery_disabled"
        return result

    state_dir = hermes_home / "state"
    watermark = _read_watermark(state_dir)

    entries, updated_last_mtime = _scan_sessions(hermes_home, watermark)
    result["scanned"] = len(entries)

    if entries:
        ok = _rewrite_memory_block(memory_path, entries)
        if ok:
            result["appended"] = len(entries)
        else:
            result["errors"] = len(entries)
    # Always persist watermark (captures new message indices from scanned sessions)

    # Persist watermark even when no new entries (captures new message indices)
    watermark["last_session_mtime_ns"] = updated_last_mtime
    _write_watermark(state_dir, watermark)

    result["done"] = True
    return result


# ---------------------------------------------------------------------------
# Script entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    hermes_home = os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))
    hermes_arg = None

    args = sys.argv[1:]
    if "--hermes-home" in args:
        idx = args.index("--hermes-home")
        if idx + 1 < len(args):
            hermes_home = args[idx + 1]
        else:
            print(json.dumps({"error": "missing --hermes-home value", "done": False}), file=sys.stderr)
            sys.exit(2)
        hermes_arg = hermes_home

    result = sync(Path(hermes_home))

    # Close the check-in → facet → baseline loop. Pending check-in replies are
    # otherwise never processed (facet_updater was not wired into any cron),
    # leaving subject_baseline.json unconsolidated. Fail-open: never break the
    # no-agent cron stdout contract. Single-host pilot: process every subject
    # under RELIC_HOME that has pending replies.
    facet_result = _process_pending_facets()
    result["facet_processing"] = facet_result

    # Status to stderr only — no-agent cron delivers stdout, must stay silent on success.
    print(json.dumps(result, ensure_ascii=False), file=sys.stderr)

    if not result.get("done"):
        sys.exit(1)


def _process_pending_facets() -> dict[str, Any]:
    """Process pending check-in replies into facet observations + baseline.

    Fail-open and side-effect-safe: any error is captured and returned, never
    raised, so the cron's stdout delivery contract is preserved.
    """
    summary: dict[str, Any] = {"subjects": {}, "error": None}
    try:
        import sqlite3 as _sqlite3
        from relic.checkin.facet_updater import process_pending_exchanges

        relic_home = Path(os.environ.get("RELIC_HOME", str(Path.home() / ".relic")))
        subjects_dir = relic_home / "subjects"
        if not subjects_dir.is_dir():
            return summary

        only = os.environ.get("RELIC_SUBJECT_ID", "").strip()
        for subject_path in sorted(subjects_dir.iterdir()):
            if not subject_path.is_dir():
                continue
            subject_id = subject_path.name
            if only and subject_id != only:
                continue
            db_path = subject_path / "relic.db"
            baseline_path = subject_path / "subject_baseline.json"
            if not db_path.exists() or not baseline_path.exists():
                continue
            try:
                conn = _sqlite3.connect(str(db_path))
                results = process_pending_exchanges(
                    conn, baseline_path, subject_id, dry_run=False,
                )
                conn.close()
                if results:
                    summary["subjects"][subject_id] = {
                        "processed": len(results),
                        "informative": sum(1 for r in results if r.get("informative")),
                    }
            except Exception as exc:  # per-subject isolation
                summary["subjects"][subject_id] = {"error": str(exc)}
    except Exception as exc:
        summary["error"] = str(exc)
    return summary


if __name__ == "__main__":
    main()
