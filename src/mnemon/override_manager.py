"""CLI per gestire override e rollback dei monitor Paperclip.

Usage:
  python3 -m mnemon.override_manager status
  python3 -m mnemon.override_manager list [team]
  python3 -m mnemon.override_manager rollback <team> [--to TIMESTAMP]
  python3 -m mnemon.override_manager clear <team>

Teams: health, humanness
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

RELIC_DIR = Path(
    os.environ.get("RELIC_DATA_DIR")
    or str(Path(__file__).resolve().parent)
)

TEAMS: dict[str, Path] = {
    "health":    RELIC_DIR / "health_overrides.json",
    "humanness": RELIC_DIR / "humanness_overrides.json",
}


# ── Comandi ───────────────────────────────────────────────────────────────────

def cmd_status(_args: argparse.Namespace) -> None:
    from mnemon.relic_override_store import get_active_overrides, list_snapshots

    print("\n== Relic Override Status ==\n")
    for team, override_file in TEAMS.items():
        data = get_active_overrides(override_file)
        snaps = list_snapshots(RELIC_DIR, team)

        if data:
            sev = data.get("severity", "?").upper()
            exp = (data.get("expires_at") or "?")[:19]
            constraints = [
                k for k in data
                if k not in ("severity", "generated_at", "expires_at")
            ]
            print(f"  {team:12s}  [{sev}]  vincoli: {', '.join(constraints) or '—'}")
            print(f"               Scade: {exp}")
        else:
            print(f"  {team:12s}  [--]  nessun override attivo")

        print(f"               Snapshot: {len(snaps)} disponibili", end="")
        if snaps:
            print(f"  (ultimo: {snaps[0]['timestamp']})", end="")
        print()

    print()


def cmd_list(args: argparse.Namespace) -> None:
    from mnemon.relic_override_store import list_snapshots

    teams = [args.team] if args.team else list(TEAMS.keys())
    for team in teams:
        snaps = list_snapshots(RELIC_DIR, team)
        print(f"\n== {team} — {len(snaps)} snapshot ==")
        if not snaps:
            print("  (nessuno)")
            continue
        for s in snaps[:15]:
            c = ", ".join(s["constraints"]) or "—"
            print(f"  {s['timestamp']}  severity={s['severity']}  vincoli=[{c}]")


def cmd_rollback(args: argparse.Namespace) -> None:
    from mnemon.relic_override_store import restore_snapshot

    team = args.team
    result = restore_snapshot(RELIC_DIR, team, TEAMS[team], timestamp=args.to)
    if "error" in result:
        print(f"Errore: {result['error']}")
        sys.exit(1)
    c = ", ".join(result.get("constraints", [])) or "—"
    print(f"Rollback '{team}' → snapshot {result['restored']} "
          f"(severity={result['severity']}, vincoli=[{c}])")


def cmd_clear(args: argparse.Namespace) -> None:
    from mnemon.relic_override_store import clear_override

    result = clear_override(RELIC_DIR, args.team, TEAMS[args.team])
    if result["status"] == "cleared":
        print(f"Override '{args.team}' rimosso. Sistema torna ai default.")
    else:
        print(f"Override '{args.team}' già assente.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Relic Override Manager — rollback e gestione override Paperclip",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Esempi:\n"
            "  python3 -m mnemon.override_manager status\n"
            "  python3 -m mnemon.override_manager list humanness\n"
            "  python3 -m mnemon.override_manager rollback humanness\n"
            "  python3 -m mnemon.override_manager rollback humanness --to 20260424_080000\n"
            "  python3 -m mnemon.override_manager clear health\n"
        ),
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("status", help="Mostra override attivi e snapshot disponibili")

    p_list = sub.add_parser("list", help="Lista snapshot per team")
    p_list.add_argument(
        "team", nargs="?", choices=list(TEAMS),
        help="Team specifico (ometti per tutti)"
    )

    p_rb = sub.add_parser("rollback", help="Ripristina lo snapshot precedente")
    p_rb.add_argument("team", choices=list(TEAMS))
    p_rb.add_argument(
        "--to", metavar="TIMESTAMP",
        help="Timestamp specifico da ripristinare (es. 20260424_080000)"
    )

    p_cl = sub.add_parser("clear", help="Rimuove override attivo (torna a default)")
    p_cl.add_argument("team", choices=list(TEAMS))

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return 1

    {"status": cmd_status, "list": cmd_list,
     "rollback": cmd_rollback, "clear": cmd_clear}[args.cmd](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
