"""Chronicle CLI — unified inspection tool for Relic event store.

Module: relic.chronicle.cli.main
Entry: chronicle query|timeline|decision|snapshot|provenance|stats|export|delete|reaper|report
Reference: docs/chronicle/agentic-development-plan.md §1.4, T071-T080
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from relic.chronicle import access_audit

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def _format_json(data: list[dict] | dict) -> str:
    return json.dumps(data, indent=2, sort_keys=True, default=str)


def _audit_read(
    args: argparse.Namespace,
    kind: str,
    filters: dict[str, object],
    rows_returned: int,
    result_data: object,
) -> None:
    """Log researcher-mode read access unless the command opted out."""
    if getattr(args, "no_audit", False):
        return
    from relic.chronicle.access_audit import log_access

    log_access(
        accessor_id=getattr(args, "accessor", None) or "researcher:cli",
        access_kind=kind,
        target_filter={key: value for key, value in filters.items() if value is not None},
        rows_returned=rows_returned,
        result_data=result_data,
    )


def _format_table(data: list[dict], columns: list[str] | None = None) -> str:
    if not data:
        return "(no results)"
    cols = columns or list(data[0].keys())
    # Filter to available columns
    cols = [c for c in cols if any(c in row for row in data)]
    widths = {c: max(len(c), max(len(str(row.get(c, ""))) for row in data)) for c in cols}
    header = "  ".join(c.ljust(widths[c]) for c in cols)
    sep = "  ".join("-" * widths[c] for c in cols)
    rows = []
    for row in data:
        rows.append("  ".join(str(row.get(c, "")).ljust(widths[c])[:widths[c]] for c in cols))
    return f"{header}\n{sep}\n" + "\n".join(rows)


# ---------------------------------------------------------------------------
# Subcommand: query
# ---------------------------------------------------------------------------

def cmd_query(args: argparse.Namespace) -> int:
    from relic.chronicle.reader import query_events
    from relic.chronicle import context as pctx

    # Register trace context for audit
    if not args.no_audit:
        trace_id = uuid.uuid4()
        pctx.set_trace_id(trace_id)

    results = query_events(
        trace_id=args.trace or None,
        session_id=args.session or None,
        subject_id=args.subject or None,
        event_type=args.type or None,
        event_category=args.category or None,
        source_module=args.module or None,
        since=args.since or None,
        until=args.until or None,
        limit=args.limit,
    )

    if not args.no_audit:
        access_audit.log_query(
            accessor_id=args.accessor or "researcher:cli",
            filters={
                "trace_id": str(args.trace) if args.trace else None,
                "session_id": str(args.session) if args.session else None,
                "subject_id": args.subject,
                "event_type": args.type,
                "event_category": args.category,
                "source_module": args.module,
            },
            rows_returned=len(results),
            trace_id=trace_id if not args.no_audit else None,
        )

    if args.format == "json":
        print(_format_json(results))
    elif args.format == "jsonl":
        for row in results:
            print(json.dumps(row, default=str))
    else:
        print(_format_table(results))

    return 0


# ---------------------------------------------------------------------------
# Subcommand: timeline
# ---------------------------------------------------------------------------

def cmd_timeline(args: argparse.Namespace) -> int:
    from relic.chronicle.reader import query_events

    results = query_events(
        trace_id=args.trace or None,
        session_id=args.session or None,
        subject_id=args.subject or None,
        since=args.since or None,
        until=args.until or None,
        limit=args.limit,
    )

    _audit_read(
        args,
        "timeline",
        {
            "trace_id": args.trace,
            "session_id": args.session,
            "subject_id": args.subject,
            "since": args.since,
            "until": args.until,
        },
        len(results),
        results,
    )

    if not results:
        print("(no events found)")
        return 0

    # Group by trace or session for timeline display
    if args.group_by == "trace":
        groups: dict[str, list] = {}
        for row in results:
            key = row.get("trace_id", "unknown")
            groups.setdefault(key, []).append(row)
        for trace_id, events in groups.items():
            print(f"\n=== Trace {trace_id[:8]}... ({len(events)} events) ===")
            for e in reversed(events):
                ts = e.get("timestamp", "")[:19]
                et = e.get("event_type", "?")
                src = e.get("source_module", "?")
                dur = e.get("duration_ms")
                dur_str = f" [{dur:.1f}ms]" if dur else ""
                print(f"  {ts}  {et}{dur_str}  [{src.split('.')[-1]}]")
    else:
        for row in results:
            ts = row.get("timestamp", "")[:19]
            et = row.get("event_type", "?")
            sev = row.get("severity", "info")
            src = row.get("source_module", "?")[:40]
            dur = row.get("duration_ms")
            dur_str = f" {dur:.1f}ms" if dur else ""
            print(f"{ts} {sev:8} {et:30}{dur_str}  {src}")

    return 0


# ---------------------------------------------------------------------------
# Subcommand: decision
# ---------------------------------------------------------------------------

def cmd_decision(args: argparse.Namespace) -> int:
    from relic.chronicle.reader import query_decisions

    results = query_decisions(
        trace_id=args.trace or None,
        session_id=args.session or None,
        subject_id=args.subject or None,
        decision_kind=args.kind or None,
        limit=args.limit,
    )

    _audit_read(
        args,
        "decision",
        {
            "trace_id": args.trace,
            "session_id": args.session,
            "subject_id": args.subject,
            "decision_kind": args.kind,
        },
        len(results),
        results,
    )

    if args.format == "json":
        print(_format_json(results))
    else:
        for d in results:
            ts = d.get("timestamp", "")[:19]
            dk = d.get("decision_kind", "?")
            actor = d.get("actor_id", "?")
            status = d.get("validation_status", "?")
            rat = d.get("rationale_summary", "")[:60]
            conf = d.get("confidence")
            conf_str = f" conf={conf:.2f}" if conf else ""
            print(f"{ts}  {dk:25}  actor={actor:20} status={status:10}{conf_str}")
            if rat:
                print(f"         rationale: {rat}")

    return 0


# ---------------------------------------------------------------------------
# Subcommand: snapshot
# ---------------------------------------------------------------------------

def cmd_snapshot(args: argparse.Namespace) -> int:
    from relic.chronicle.reader import query_snapshots

    results = query_snapshots(
        subject_id=args.subject or None,
        snapshot_type=args.type or None,
        scope_ref=args.scope or None,
        limit=args.limit,
    )

    _audit_read(
        args,
        "snapshot",
        {"subject_id": args.subject, "snapshot_type": args.type, "scope_ref": args.scope},
        len(results),
        results,
    )

    if args.format == "json":
        print(_format_json(results))
    else:
        for s in results:
            ts = s.get("captured_at", "")[:19]
            stype = s.get("snapshot_type", "?")
            ref = s.get("scope_ref", "")
            hash_ = s.get("content_hash", "")[:20]
            diff = s.get("diff_from_previous")
            diff_str = f"  diff={len(diff.get('added', []))}a/{len(diff.get('removed', []))}r" if diff else ""
            print(f"{ts}  {stype:25}  ref={ref[:30]:30}  hash={hash_}{diff_str}")

    return 0


# ---------------------------------------------------------------------------
# Subcommand: provenance
# ---------------------------------------------------------------------------

def cmd_provenance(args: argparse.Namespace) -> int:
    from relic.chronicle.provenance import get_ancestors, get_descendants, verify_artifact_provenance

    aid = uuid.UUID(args.artifact)
    direction = args.direction or "ancestors"
    depth = args.depth or 3

    if direction == "ancestors":
        nodes = get_ancestors(aid, depth=depth)
        _audit_read(args, "provenance", {"artifact_id": str(aid), "direction": direction}, len(nodes), nodes)
        print(f"Ancestors of {aid} (depth={depth}):")
        for n in nodes:
            rel = n.get("relation", "?")
            ntype = n.get("from_node_type", "?")
            nid = str(n.get("from_node_id", ""))[:8]
            dep = n.get("depth", "?")
            print(f"  [{dep}] {rel:25}  {ntype:10}  {nid}...")
    elif direction == "descendants":
        nodes = get_descendants(aid, depth=depth)
        _audit_read(args, "provenance", {"artifact_id": str(aid), "direction": direction}, len(nodes), nodes)
        print(f"Descendants of {aid} (depth={depth}):")
        for n in nodes:
            rel = n.get("relation", "?")
            atype = n.get("artifact_id", "")[:8]
            dep = n.get("depth", "?")
            print(f"  [{dep}] {rel:25}  → artifact {atype}...")
    elif direction == "verify":
        valid, missing = verify_artifact_provenance(aid)
        _audit_read(
            args,
            "provenance",
            {"artifact_id": str(aid), "direction": direction},
            1,
            {"valid": valid, "missing": missing},
        )
        if valid:
            print(f"✓ Provenance for {aid} is valid (all upstream nodes exist)")
        else:
            print(f"✗ Provenance incomplete for {aid}")
            for m in missing:
                print(f"  MISSING: {m}")
            return 1

    return 0


# ---------------------------------------------------------------------------
# Subcommand: stats
# ---------------------------------------------------------------------------

def cmd_stats(args: argparse.Namespace) -> int:
    from relic.chronicle.reader import stats

    result = stats(subject_id=args.subject or None, since=args.since or None)

    _audit_read(
        args,
        "query",
        {"command": "stats", "subject_id": args.subject, "since": args.since},
        int(result.get("total_events", 0) or 0),
        result,
    )

    if args.format == "json":
        print(_format_json(result))
    else:
        print(f"Total events:  {result.get('total_events', 0)}")
        print(f"Total decisions: {result.get('total_decisions', 0)}")
        print(f"Total snapshots: {result.get('total_snapshots', 0)}")
        if result.get("by_event_type"):
            print("\nBy event_type:")
            for item in result["by_event_type"][:10]:
                print(f"  {item['type']:30}  {item['count']:6}")
        if result.get("by_severity"):
            print("\nBy severity:")
            for item in result["by_severity"]:
                print(f"  {item['severity']:10}  {item['count']:6}")
        if result.get("by_sensitivity"):
            print("\nBy sensitivity:")
            for item in result["by_sensitivity"]:
                print(f"  {item['sensitivity']:15}  {item['count']:6}")

    return 0


# ---------------------------------------------------------------------------
# Subcommand: export
# ---------------------------------------------------------------------------

def cmd_export(args: argparse.Namespace) -> int:
    from relic.chronicle.reader import query_events, query_decisions, query_snapshots
    from relic.chronicle.access_audit import log_export
    import tarfile
    import tempfile
    import shutil

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    subject_id = args.subject

    # Gather data
    events = query_events(subject_id=subject_id, limit=10000)
    decisions = query_decisions(subject_id=subject_id, limit=5000)
    snapshots = query_snapshots(subject_id=subject_id, limit=1000)

    # Write files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        events_file = tmp_path / "chronicle_events.jsonl"
        with open(events_file, "w", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(e, default=str) + "\n")

        decisions_file = tmp_path / "chronicle_decisions.jsonl"
        with open(decisions_file, "w", encoding="utf-8") as f:
            for d in decisions:
                f.write(json.dumps(d, default=str) + "\n")

        snapshots_file = tmp_path / "chronicle_state_snapshots.jsonl"
        with open(snapshots_file, "w", encoding="utf-8") as f:
            for s in snapshots:
                f.write(json.dumps(s, default=str) + "\n")

        manifest = {
            "subject_id": subject_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "events_count": len(events),
            "decisions_count": len(decisions),
            "snapshots_count": len(snapshots),
            "schema_versions": ["chronicle-event/v1", "chronicle-decision/v1", "chronicle-snapshot/v1"],
            "redaction_applied": True,
        }
        with open(tmp_path / "MANIFEST.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Create tar
        with tarfile.open(output_path, "w:gz") as tar:
            tar.add(events_file, arcname="chronicle_events.jsonl")
            tar.add(decisions_file, arcname="chronicle_decisions.jsonl")
            tar.add(snapshots_file, arcname="chronicle_state_snapshots.jsonl")
            tar.add(tmp_path / "MANIFEST.json", arcname="MANIFEST.json")

    size_bytes = output_path.stat().st_size

    log_export(
        accessor_id=args.accessor or "researcher:cli",
        subject_id=subject_id or "unknown",
        format="tar.gz",
        bytes_written=size_bytes,
    )

    print(f"Exported to {output_path} ({size_bytes:,} bytes)")
    print(f"  events: {len(events)}, decisions: {len(decisions)}, snapshots: {len(snapshots)}")

    return 0


# ---------------------------------------------------------------------------
# Subcommand: delete
# ---------------------------------------------------------------------------

def cmd_delete(args: argparse.Namespace) -> int:
    from relic.chronicle.reader import _get_db_connection
    from relic.chronicle.retention import purge_subject_records
    from relic.chronicle.access_audit import log_delete

    subject_id = args.subject
    dry_run = args.dry_run

    if dry_run:
        conn = _get_db_connection()
        results = {
            "dry_run": True,
            "subject_id": subject_id,
            "chronicle_events_deleted": conn.execute(
                "SELECT COUNT(*) FROM chronicle_events WHERE subject_id = ?", (subject_id,)
            ).fetchone()[0],
            "chronicle_decisions_deleted": conn.execute(
                "SELECT COUNT(*) FROM chronicle_decisions WHERE subject_id = ?", (subject_id,)
            ).fetchone()[0],
            "chronicle_state_snapshots_deleted": conn.execute(
                "SELECT COUNT(*) FROM chronicle_state_snapshots WHERE subject_id = ?", (subject_id,)
            ).fetchone()[0],
            "chronicle_provenance_edges_deleted": 0,
        }
        if args.cascade:
            results["chronicle_provenance_edges_deleted"] = conn.execute(
                """
                SELECT COUNT(*) FROM chronicle_provenance_edges
                WHERE from_node_id IN (
                    SELECT event_id FROM chronicle_events WHERE subject_id = ?
                )
                OR trace_id IN (
                    SELECT trace_id FROM chronicle_events WHERE subject_id = ?
                    UNION
                    SELECT trace_id FROM chronicle_decisions WHERE subject_id = ?
                    UNION
                    SELECT trace_id FROM chronicle_state_snapshots WHERE subject_id = ?
                )
                """,
                (subject_id, subject_id, subject_id, subject_id),
            ).fetchone()[0]
        conn.close()
    else:
        results = purge_subject_records(subject_id, cascade=args.cascade)

    if args.format == "json":
        print(_format_json(results))
    else:
        total = (
            results.get("chronicle_events_deleted", 0)
            + results.get("chronicle_decisions_deleted", 0)
            + results.get("chronicle_state_snapshots_deleted", 0)
            + results.get("chronicle_provenance_edges_deleted", 0)
        )
        print(f"{'DRY-RUN: ' if dry_run else ''}Deleted: records={total}")

    if not dry_run:
        log_delete(
            accessor_id=args.accessor or "researcher:cli",
            subject_id=subject_id or "unknown",
            rows_deleted=results.get("chronicle_events_deleted", 0),
            cascade=args.cascade or False,
        )

    return 0


# ---------------------------------------------------------------------------
# Subcommand: reaper
# ---------------------------------------------------------------------------

def cmd_reaper(args: argparse.Namespace) -> int:
    from relic.chronicle.retention import run

    results = run(dry_run=args.dry_run, policy=args.policy or None)
    total = results.get("total_deleted", 0)

    if args.format == "json":
        print(_format_json(results))
    else:
        print(f"{'DRY-RUN: ' if results.get('dry_run') else ''}Reaper complete. Total deleted: {total}")

    return 0


# ---------------------------------------------------------------------------
# Subcommand: verify (JSONL visibility check)
# ---------------------------------------------------------------------------

# Maps the discriminating primary-key column found in a journal row to its
# SQLite table. The emitter writes the identical `to_db_row()` dict to both the
# JSONL journal (first) and SQLite (second), so a journal row is directly
# re-insertable into its table when SQLite is missing it.
_JOURNAL_PK_TABLE = {
    "event_id": "chronicle_events",
    "decision_id": "chronicle_decisions",
    "snapshot_id": "chronicle_state_snapshots",
    "edge_id": "chronicle_provenance_edges",
}


def _classify_journal_row(row: dict) -> tuple[str, str, str] | None:
    """Return (table, pk_column, pk_value) for a journal row, or None if unknown."""
    for pk_col, table in _JOURNAL_PK_TABLE.items():
        if row.get(pk_col):
            return table, pk_col, str(row[pk_col])
    return None


def cmd_verify(args: argparse.Namespace) -> int:
    """Reconcile the JSONL journal against SQLite.

    The emitter appends to JSONL first and inserts into SQLite second, tolerating
    a SQLite failure after the journal append (see emitter dual-write strategy).
    That can leave events present in the journal but invisible to every read path,
    which only queries SQLite. This command finds those gaps; with --repair it
    replays the missing rows back into SQLite.
    """
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)
    from pathlib import Path
    from relic.db import get_connection

    journal_dir = Path.home() / ".relic" / "chronicle" / "journal"
    if not journal_dir.exists():
        print("No journal found.")
        return 0

    print(f"Scanning {journal_dir}...")
    total_entries = 0
    total_missing = 0
    total_repaired = 0
    total_malformed = 0
    total_unclassified = 0

    conn = get_connection()
    try:
        for jf in sorted(journal_dir.glob("*.jsonl")):
            entries = missing = repaired = 0
            with open(jf, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entries += 1
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        total_malformed += 1
                        continue
                    classified = _classify_journal_row(row)
                    if classified is None:
                        total_unclassified += 1
                        continue
                    table, pk_col, pk_val = classified
                    cur = conn.execute(
                        f"SELECT 1 FROM {table} WHERE {pk_col} = ?", (pk_val,)
                    )
                    if cur.fetchone() is not None:
                        continue
                    missing += 1
                    if args.repair:
                        cols = list(row.keys())
                        placeholders = ", ".join(["?"] * len(cols))
                        try:
                            conn.execute(
                                f"INSERT OR IGNORE INTO {table} ({', '.join(cols)}) "
                                f"VALUES ({placeholders})",
                                [row[c] for c in cols],
                            )
                            repaired += 1
                        except Exception as exc:  # noqa: BLE001 - report and continue
                            logger.error(
                                f"[chronicle.verify] replay failed for {table} {pk_val}: {exc}"
                            )
            if args.repair:
                conn.commit()
            total_entries += entries
            total_missing += missing
            total_repaired += repaired
            status = f"{entries} entries"
            if missing:
                status += f", {missing} missing from SQLite"
            if repaired:
                status += f", {repaired} repaired"
            print(f"  {jf.name}: {status}")
    finally:
        conn.close()

    print(
        f"Total: {total_entries} entries, {total_missing} missing, "
        f"{total_repaired} repaired"
    )
    if total_malformed:
        print(f"  ({total_malformed} malformed journal lines skipped)")
    if total_unclassified:
        print(f"  ({total_unclassified} unclassified rows skipped)")
    if total_missing and not args.repair:
        print("Run with --repair to replay missing rows into SQLite.")
        return 1
    return 0


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="chronicle",
        description="Chronicle — unified event capture and inspection for Relic",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # query
    q = sub.add_parser("query", help="Query events")
    q.add_argument("--trace", help="Filter by trace_id")
    q.add_argument("--session", help="Filter by session_id")
    q.add_argument("--subject", help="Filter by subject_id")
    q.add_argument("--type", "--event-type", dest="type", help="Filter by event_type")
    q.add_argument("--category", help="Filter by event_category")
    q.add_argument("--module", help="Filter by source_module prefix")
    q.add_argument("--since", help="ISO8601 start time")
    q.add_argument("--until", help="ISO8601 end time")
    q.add_argument("--limit", type=int, default=100)
    q.add_argument("--format", choices=["json", "jsonl", "table"], default="table")
    q.add_argument("--accessor", default="researcher:cli")
    q.add_argument("--no-audit", action="store_true")
    q.set_defaults(func=cmd_query)

    # timeline
    t = sub.add_parser("timeline", help="Show event timeline")
    t.add_argument("--trace")
    t.add_argument("--session")
    t.add_argument("--subject")
    t.add_argument("--since")
    t.add_argument("--until")
    t.add_argument("--limit", type=int, default=200)
    t.add_argument("--group-by", choices=["trace", "time"], default="time")
    t.add_argument("--accessor", default="researcher:cli")
    t.add_argument("--no-audit", action="store_true")
    t.set_defaults(func=cmd_timeline)

    # decision
    d = sub.add_parser("decision", help="Query decisions")
    d.add_argument("--trace")
    d.add_argument("--session")
    d.add_argument("--subject")
    d.add_argument("--kind", help="decision_kind")
    d.add_argument("--limit", type=int, default=100)
    d.add_argument("--format", choices=["json", "table"], default="table")
    d.add_argument("--accessor", default="researcher:cli")
    d.add_argument("--no-audit", action="store_true")
    d.set_defaults(func=cmd_decision)

    # snapshot
    s = sub.add_parser("snapshot", help="Query state snapshots")
    s.add_argument("--subject")
    s.add_argument("--type", help="snapshot_type")
    s.add_argument("--scope")
    s.add_argument("--limit", type=int, default=50)
    s.add_argument("--format", choices=["json", "table"], default="table")
    s.add_argument("--accessor", default="researcher:cli")
    s.add_argument("--no-audit", action="store_true")
    s.set_defaults(func=cmd_snapshot)

    # provenance
    p = sub.add_parser("provenance", help="Show artifact provenance")
    p.add_argument("--artifact", required=True)
    p.add_argument("--direction", choices=["ancestors", "descendants", "verify"], default="ancestors")
    p.add_argument("--depth", type=int, default=3)
    p.add_argument("--accessor", default="researcher:cli")
    p.add_argument("--no-audit", action="store_true")
    p.set_defaults(func=cmd_provenance)

    # stats
    st = sub.add_parser("stats", help="Aggregate statistics")
    st.add_argument("--subject")
    st.add_argument("--since")
    st.add_argument("--format", choices=["json", "table"], default="table")
    st.add_argument("--accessor", default="researcher:cli")
    st.add_argument("--no-audit", action="store_true")
    st.set_defaults(func=cmd_stats)

    # export
    e = sub.add_parser("export", help="Export subject data as tar.gz")
    e.add_argument("--subject", required=True)
    e.add_argument("--output", required=True)
    e.add_argument("--accessor", default="researcher:cli")
    e.set_defaults(func=cmd_export)

    # delete
    del_p = sub.add_parser("delete", help="Delete subject data (GDPR)")
    del_p.add_argument("--subject", required=True)
    del_p.add_argument("--dry-run", action="store_true")
    del_p.add_argument("--cascade", action="store_true")
    del_p.add_argument("--format", choices=["json", "table"], default="table")
    del_p.add_argument("--accessor", default="researcher:cli")
    del_p.set_defaults(func=cmd_delete)

    # reaper
    rp = sub.add_parser("reaper", help="Run retention reaper")
    rp.add_argument("--dry-run", action="store_true")
    rp.add_argument("--policy")
    rp.add_argument("--format", choices=["json", "table"], default="table")
    rp.set_defaults(func=cmd_reaper)

    # verify
    v = sub.add_parser("verify", help="Verify JSONL journal visibility")
    v.set_defaults(func=cmd_verify)

    args = parser.parse_args(argv)

    try:
        return args.func(args)
    except Exception as exc:
        logger.error(f"[chronicle] {args.command} failed: {exc}", exc_info=True)
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
