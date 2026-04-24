"""Cron entrypoint: relic:goals

Invoked as: python -m relic.goals
Schedule:   30 5 1 * *

Monthly goal architecture extraction: identifies current concerns,
personal projects, and goal-linked personality facets.
"""
from relic.relic_goals import main

if __name__ == "__main__":
    main()
