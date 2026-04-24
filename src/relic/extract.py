"""Cron entrypoint: relic:extract

Invoked as: python -m relic.extract
Schedule:   0 */2 * * *   (every 2 hours)

Reads new messages from inbox.jsonl, calls LLM to extract personality
signals, and inserts observations into the SQLite database.
"""
from relic.relic_extractor import main

if __name__ == "__main__":
    main()
