#!/usr/bin/env python3
"""Load a fixture into the database."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from relic.db import init_db, load_fixture
from relic.db.loader import iter_fixtures
from relic.paths import get_db_path, get_fixtures_dir


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Load a fixture into the database.")
    parser.add_argument(
        "fixture_name",
        nargs="?",
        help="Name of fixture to load (omit to list available fixtures)"
    )
    parser.add_argument(
        "--list", "-l", action="store_true",
        help="List available fixtures"
    )
    parser.add_argument(
        "--path", type=Path,
        help="Custom database path"
    )
    args = parser.parse_args()
    
    if args.list or not args.fixture_name:
        fixtures = list(iter_fixtures())
        if fixtures:
            print("Available fixtures:")
            for name in fixtures:
                print(f"  - {name}")
        else:
            print("No fixtures found")
        return 0
    
    fixture_name = args.fixture_name
    
    try:
        if args.path:
            init_db(args.path)
        load_fixture(fixture_name, args.path)
        print(f"Loaded fixture: {fixture_name}")
        return 0
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Error loading fixture: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
