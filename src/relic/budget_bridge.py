"""Cron entrypoint: relic:budget-bridge

Invoked as: python -m relic.budget_bridge
Schedule:   20 4 * * *

Nightly Actual Budget bridge: imports financial transaction summaries
and converts them to lifestyle and stress-related observations.
"""
from relic.relic_budget_bridge import main

if __name__ == "__main__":
    main()
