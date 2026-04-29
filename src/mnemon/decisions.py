"""Cron entrypoint: relic:decisions

Invoked as: python -m relic.decisions
Schedule:   15 4 * * *

Daily decision extraction: detects explicit choices in messages and
stores them with linked personality facets for coherence analysis.
"""
from mnemon.relic_decisions import main

if __name__ == "__main__":
    main()
