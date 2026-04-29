"""Cron entrypoint: relic:passive-scan

Invoked as: python -m relic.passive_scan
Schedule:   0 */6 * * *   (every 6 hours)

Scans relational-agent session transcripts for behavioral meta-signals
and inserts observations into the SQLite database.
Requires RELIC_RELATIONAL_AGENT to be set.
"""
from mnemon.relic_passive_observer import main

if __name__ == "__main__":
    main()
