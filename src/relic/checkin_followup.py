"""Cron entrypoint: relic:checkin-followup

Invoked as: python -m relic.checkin_followup
Schedule:   on-demand (triggered by the relic-capture hook when a
            check-in reply is detected in inbox.jsonl)

Reads the pending-checkin.json signal file, acknowledges the reply,
and records the exchange in the database.
"""
from relic.relic_reply_extractor import main

if __name__ == "__main__":
    main()
