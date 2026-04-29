"""Cron entrypoint: relic:defenses

Invoked as: python -m relic.defenses
Schedule:   30 5 3 * *

Monthly defense mechanism detection: identifies mature, neurotic, and
immature defenses from behavioral and linguistic patterns.
"""
from mnemon.relic_defenses import main

if __name__ == "__main__":
    main()
