"""Cron entrypoint: relic:memory

Invoked as: python -m relic.memory
Schedule:   0 5 * * 0

Weekly memory consolidation (Sunday): computes communication metrics
from the message corpus and stores them in the memory layer.
"""
from relic.relic_memory import main

if __name__ == "__main__":
    main()
