"""Cron entrypoint: relic:narrative

Invoked as: python -m relic.narrative
Schedule:   0 6 3 * *

Monthly narrative identity analysis: extracts the subject's self-story
structure, redemption sequences, and contamination sequences.
"""
from mnemon.relic_narrative import main

if __name__ == "__main__":
    main()
