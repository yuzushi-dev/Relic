"""Cron entrypoint: relic:portrait

Invoked as: python -m relic.portrait
Schedule:   0 6 1 * *

Monthly full portrait synthesis: generates the comprehensive narrative
personality portrait from all accumulated constructs and facets.
"""
from mnemon.relic_portrait import main

if __name__ == "__main__":
    main()
