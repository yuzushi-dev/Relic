"""Cron entrypoint: relic:health-monitor

Invoked as: python -m relic.health_monitor
Schedule:   0 */12 * * *
"""
from relic.relic_health_monitor import main

if __name__ == "__main__":
    main()
