"""Cron entrypoint: relic:humanness-monitor

Invocato come: python -m relic.humanness_monitor
Schedule:      0 8 * * *
"""
from relic.relic_humanness_analyst import main

if __name__ == "__main__":
    main()
