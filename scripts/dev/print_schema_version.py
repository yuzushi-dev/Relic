#!/usr/bin/env python3
"""Print the current schema version from the database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from relic.db import get_connection
from relic.paths import get_db_path


def print_schema_version(db_path: Path | None = None) -> int:
    """Print the current schema version."""
    path = db_path or get_db_path()
    
    if not path.exists():
        print("Database not initialized")
        return 1
    
    conn = get_connection(path)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT version, applied_at FROM schema_version ORDER BY applied_at DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            print(f"Schema version: {row[0]} (applied: {row[1]})")
            return 0
        else:
            print("No schema version recorded")
            return 1
    finally:
        conn.close()


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Print the current schema version.")
    parser.add_argument(
        "--path", type=Path,
        help="Custom database path"
    )
    args = parser.parse_args()
    
    return print_schema_version(args.path)


if __name__ == "__main__":
    sys.exit(main())
