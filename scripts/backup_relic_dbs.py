#!/usr/bin/env python3
"""Verified, rotating snapshots of the live Relic SQLite databases.

Runs against databases that gateways are actively writing, so it uses SQLite's
online backup API rather than a file copy: a plain ``cp`` of a WAL database
yields a torn snapshot unless the sidecar files come with it.

The destructive half is rotation, so it is ordered defensively: a snapshot is
written to a temporary name, verified, and only then renamed into place and used
to justify deleting an older one. A run that fails verification deletes nothing.
"""

from __future__ import annotations

import fcntl
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# A week of daily snapshots. Value-level corruption (right row counts, wrong
# contents) is invisible to the checks below, so the practical defence is having
# enough history to notice it before the window closes.
KEEP = 7
FREE_SPACE_SLACK_BYTES = 512 * 1024 * 1024
# Row counts drift down a little through TTL expiry and cleanup; a drop past this
# is treated as data loss rather than churn.
SHRINK_TOLERANCE = 0.10
STAMP_RE = re.compile(r"^(?P<slug>[a-z0-9_]+)\.(?P<stamp>\d{8}T\d{6}Z)\.sqlite$")


def relic_home() -> Path:
    return Path(os.environ.get("RELIC_HOME", Path.home() / ".relic"))


def discover_databases(home: Path) -> dict[str, Path]:
    """Map slug -> live database path. Slugs are filesystem-safe and stable."""
    found: dict[str, Path] = {}
    root_db = home / "relic.db"
    if root_db.exists():
        found["relic"] = root_db
    subjects = home / "subjects"
    if subjects.is_dir():
        for subject_dir in sorted(p for p in subjects.iterdir() if p.is_dir()):
            subject = re.sub(r"[^a-z0-9]+", "_", subject_dir.name.lower())
            for name in ("relic.db", "continuity.db"):
                db = subject_dir / name
                if db.exists():
                    found[f"subject_{subject}_{name[:-3]}"] = db
    return found


def check_free_space(home: Path, databases: dict[str, Path]) -> None:
    """Refuse to run when the disk cannot comfortably hold another full set.

    This host has already taken an outage from a full root filesystem, and a
    backup job is a plausible way to cause the next one. Bailing out early keeps
    the existing verified copies untouched.
    """
    needed = sum(db.stat().st_size for db in databases.values()) * 2 + FREE_SPACE_SLACK_BYTES
    free = shutil.disk_usage(home).free
    if free < needed:
        raise RuntimeError(
            f"refusing to back up: {free / 1e6:.0f}MB free, "
            f"need {needed / 1e6:.0f}MB (databases + retention + slack)"
        )


def snapshot(source: Path, destination: Path) -> None:
    """Write a self-contained snapshot of a live database.

    Opened read-only so a backup run can never mutate the source, and the
    destination is collapsed out of WAL so the artifact is a single file that
    restores correctly on its own.
    """
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=30.0)
    dst = sqlite3.connect(str(destination), timeout=30.0)
    try:
        src.backup(dst)
        dst.commit()
        dst.execute("PRAGMA journal_mode = DELETE")
    finally:
        dst.close()
        src.close()


def verify(source: Path, candidate: Path) -> None:
    """Fail loudly unless the snapshot is readable, sound, and complete.

    Table count is compared against the source because ``integrity_check`` passes
    happily on a structurally valid but empty database, which is exactly what a
    truncated or short-circuited backup looks like.
    """
    if candidate.stat().st_size == 0:
        raise RuntimeError(f"{candidate.name}: empty snapshot")
    conn = sqlite3.connect(f"file:{candidate}?mode=ro", uri=True, timeout=30.0)
    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=30.0)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"{candidate.name}: integrity check failed: {result}")
        query = "SELECT count(*) FROM sqlite_master WHERE type='table'"
        got = conn.execute(query).fetchone()[0]
        expected = src.execute(query).fetchone()[0]
        if got < expected:
            raise RuntimeError(
                f"{candidate.name}: {got} tables, source has {expected}"
            )
    finally:
        src.close()
        conn.close()


def row_census(path: Path) -> int:
    """Total rows across user tables: a cheap proxy for how much data is in here.

    Costs single-digit milliseconds even on the largest database here, because
    SQLite answers per-table counts from its own structures rather than scanning.
    """
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30.0)
    try:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        return sum(
            conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
            for table in tables
        )
    finally:
        conn.close()


def prune(
    slug_dir: Path, backups_root: Path, keep: int, just_written: Path
) -> tuple[list[str], list[str]]:
    """Delete the oldest snapshots beyond ``keep``, and nothing else.

    Deletion is restricted three ways: the filename must match the snapshot
    pattern, the resolved path must sit inside the backups root, and the file
    just verified is never a candidate. Live databases live outside this tree and
    do not match the pattern, so they cannot be selected even if this is pointed
    somewhere unexpected.

    On top of that, a snapshot holding materially more data than the one
    replacing it is kept regardless of age. ``integrity_check`` only proves a file
    is structurally sound, so a database that got emptied by a bad repair or a
    half-finished migration backs up perfectly and would otherwise evict the last
    copy that still had the rows. Growth is the normal direction here, so this
    only trips when something went wrong.
    """
    snapshots = sorted(
        (p for p in slug_dir.iterdir() if STAMP_RE.match(p.name) and p != just_written),
        key=lambda p: STAMP_RE.match(p.name).group("stamp"),
    )
    floor = row_census(just_written) * (1 + SHRINK_TOLERANCE)
    removed: list[str] = []
    protected: list[str] = []
    for stale in snapshots[: max(0, len(snapshots) + 1 - keep)]:
        resolved = stale.resolve()
        if backups_root.resolve() not in resolved.parents:
            raise RuntimeError(f"refusing to delete outside backups root: {resolved}")
        if row_census(resolved) > floor:
            protected.append(stale.name)
            continue
        resolved.unlink()
        removed.append(stale.name)
    return removed, protected


def main() -> int:
    home = relic_home()
    databases = discover_databases(home)
    if not databases:
        print(f"no databases found under {home}", file=sys.stderr)
        return 1

    backups_root = home / "backups"
    backups_root.mkdir(parents=True, exist_ok=True)

    with open(backups_root / ".backup.lock", "w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        check_free_space(home, databases)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        failures = 0

        for slug, source in databases.items():
            slug_dir = backups_root / slug
            slug_dir.mkdir(parents=True, exist_ok=True)
            for leftover in slug_dir.glob("*.sqlite.tmp"):
                leftover.unlink()

            final = slug_dir / f"{slug}.{stamp}.sqlite"
            staging = final.with_suffix(".sqlite.tmp")
            try:
                snapshot(source, staging)
                verify(source, staging)
            except Exception as exc:  # keep every existing copy on any failure
                staging.unlink(missing_ok=True)
                print(f"FAIL {slug}: {exc}", file=sys.stderr)
                failures += 1
                continue

            os.replace(staging, final)
            removed, protected = prune(slug_dir, backups_root, KEEP, final)
            size = final.stat().st_size / 1e6
            note = f" (pruned {', '.join(removed)})" if removed else ""
            print(f"ok   {slug}: {size:.1f}MB{note}")
            if protected:
                # Louder than the ok line, and non-zero exit, because a shrinking
                # database is the case where quietly rotating loses the data.
                print(
                    f"WARN {slug}: kept {', '.join(protected)} — richer than the "
                    f"new snapshot ({row_census(final)} rows); inspect before "
                    f"deleting by hand",
                    file=sys.stderr,
                )
                failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
