#!/usr/bin/env python3
"""Reset the fixture database to a clean state."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from relic.db import get_connection, init_db
from relic.paths import get_db_path, get_relic_home


def reset_db(db_path: Path | None = None) -> int:
    """Reset the database by removing and recreating it."""
    path = db_path or get_db_path()
    
    if path.exists():
        path.unlink()
    
    init_db(path)
    print(f"Database reset: {path}")
    return 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Reset the fixture database.")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be done without actually resetting"
    )
    parser.add_argument(
        "--path", type=Path,
        help="Custom database path"
    )
    args = parser.parse_args()
    
    path = args.path or get_db_path()
    
    if args.dry_run:
        print(f"Would reset database: {path}")
        print("Would run all migrations")
        return 0
    
    return reset_db(path)


if __name__ == "__main__":
    sys.exit(main())
