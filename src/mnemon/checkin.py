"""Cron entrypoint: relic:checkin

Invoked as: python -m relic.checkin
Schedule:   */30 9-22 * * *   (every 30 min, active hours)

Scores all 60 facets, selects the highest gap-score facet, generates a
natural-language probe question, and delivers it via the configured channel.
"""
from mnemon.relic_question_engine import main

if __name__ == "__main__":
    main()
