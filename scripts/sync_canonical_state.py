#!/usr/bin/env python3
"""Copy canonical Relic state tables into an isolated shadow target."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _table_sql(conn: sqlite3.Connection, table: str) -> str:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    if row is None or not row["sql"]:
        raise ValueError(f"missing CREATE TABLE statement for {table}")
    return str(row["sql"])


def _table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _copy_table(
    source: sqlite3.Connection,
    target: sqlite3.Connection,
    table: str,
    *,
    recreate_on_mismatch: bool,
) -> dict[str, Any]:
    if not _table_exists(source, table):
        raise ValueError(f"source table not found: {table}")
    if not _table_exists(target, table):
        target.execute(_table_sql(source, table))
        recreated = True
    else:
        recreated = False

    source_cols = _table_columns(source, table)
    target_cols = _table_columns(target, table)
    if source_cols != target_cols:
        if not recreate_on_mismatch:
            raise ValueError(
                f"schema mismatch for {table}: source columns={source_cols} target columns={target_cols}"
            )
        quoted_table = _quote_ident(table)
        target.execute(f"DROP TABLE {quoted_table}")
        target.execute(_table_sql(source, table))
        target_cols = _table_columns(target, table)
        recreated = True

    quoted_table = _quote_ident(table)
    quoted_cols = ", ".join(_quote_ident(col) for col in source_cols)
    placeholders = ", ".join("?" for _ in source_cols)
    rows = source.execute(f"SELECT {quoted_cols} FROM {quoted_table}").fetchall()

    target.execute(f"DELETE FROM {quoted_table}")
    if rows:
        target.executemany(
            f"INSERT INTO {quoted_table} ({quoted_cols}) VALUES ({placeholders})",
            [tuple(row[col] for col in source_cols) for row in rows],
        )

    return {"rows_copied": len(rows), "columns": source_cols, "recreated": recreated}


def sync_state(
    *,
    source_data_dir: Path,
    target_data_dir: Path,
    tables: list[str],
    report_path: Path | None,
    copy_portrait: bool,
    recreate_on_mismatch: bool,
) -> dict[str, Any]:
    source_db = source_data_dir / "relic.db"
    target_db = target_data_dir / "relic.db"
    if not source_db.exists():
        raise FileNotFoundError(f"missing source db: {source_db}")
    if not target_db.exists():
        raise FileNotFoundError(f"missing target db: {target_db}")

    target_data_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "source_data_dir": str(source_data_dir),
        "target_data_dir": str(target_data_dir),
        "copied_tables": {},
        "portrait_copied": False,
    }

    source = _connect(source_db)
    target = _connect(target_db)
    try:
        target.execute("BEGIN")
        for table in tables:
            report["copied_tables"][table] = _copy_table(
                source,
                target,
                table,
                recreate_on_mismatch=recreate_on_mismatch,
            )
        target.commit()
    except Exception:
        target.rollback()
        raise
    finally:
        source.close()
        target.close()

    if copy_portrait:
        source_portrait = source_data_dir / "PORTRAIT.md"
        if not source_portrait.exists():
            raise FileNotFoundError(f"missing source portrait: {source_portrait}")
        shutil.copy2(source_portrait, target_data_dir / "PORTRAIT.md")
        report["portrait_copied"] = True

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync canonical Relic state into an isolated shadow target.")
    parser.add_argument("--source-data-dir", required=True, help="Canonical RELIC_DATA_DIR")
    parser.add_argument("--target-data-dir", required=True, help="Shadow RELIC_DATA_DIR to update in place")
    parser.add_argument("--tables", required=True, help="Comma-separated list of tables to replace from source")
    parser.add_argument("--report-path", help="Optional JSON report output path")
    parser.add_argument("--copy-portrait", action="store_true", help="Also replace PORTRAIT.md from source")
    parser.add_argument(
        "--recreate-on-mismatch",
        action="store_true",
        help="Drop and recreate target tables when their schema differs from source",
    )
    args = parser.parse_args()

    try:
        sync_state(
            source_data_dir=Path(args.source_data_dir),
            target_data_dir=Path(args.target_data_dir),
            tables=[table.strip() for table in args.tables.split(",") if table.strip()],
            report_path=Path(args.report_path) if args.report_path else None,
            copy_portrait=args.copy_portrait,
            recreate_on_mismatch=args.recreate_on_mismatch,
        )
    except (FileNotFoundError, ValueError, sqlite3.DatabaseError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("canonical state sync completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
