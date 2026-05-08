"""relic CLI entry point via python -m relic."""

from __future__ import annotations

import sys

from relic.cli import main as cli_main


def main() -> int:
    """Main entry point for python -m relic."""
    return cli_main()


if __name__ == "__main__":
    sys.exit(main())
