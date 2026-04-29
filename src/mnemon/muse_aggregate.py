"""Cron entrypoint: relic:muse-aggregate

Invoked as: python -m relic.muse_aggregate
Schedule:   30 4 * * *

Daily Muse 2 EEG session aggregation: computes focus, calm, frontal
asymmetry, and engagement metrics from completed EEG sessions.
"""
from mnemon.relic_muse_aggregator import main

if __name__ == "__main__":
    main()
