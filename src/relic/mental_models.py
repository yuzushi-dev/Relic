"""Cron entrypoint: relic:mental-models

Invoked as: python -m relic.mental_models
Schedule:   0 5 5 * *

Monthly mental model extraction: identifies stable conceptual
frameworks and reasoning heuristics the subject applies repeatedly.
"""
from relic.relic_mental_models import main

if __name__ == "__main__":
    main()
