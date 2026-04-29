"""Cron entrypoint: relic:appraisal

Invoked as: python -m relic.appraisal
Schedule:   30 4 5 * *

Monthly appraisal analysis: infers characteristic cognitive appraisal
patterns (primary/secondary) using Lazarus appraisal theory.
"""
from mnemon.relic_appraisal import main

if __name__ == "__main__":
    main()
