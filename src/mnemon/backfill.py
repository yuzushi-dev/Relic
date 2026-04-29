"""Cron entrypoint: relic:backfill

Invoked as: python -m relic.backfill
Schedule:   @manual

On-demand backfill: imports a JSONL file of past messages into
inbox.jsonl, de-duplicating by message_id.
"""
from mnemon.relic_backfill import main

if __name__ == "__main__":
    main()
