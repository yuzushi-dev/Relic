"""Cron entrypoint: relic:stress-index

Invoked as: python -m relic.stress_index
Schedule:   0 6 * * 1

Weekly stress index (Monday): computes a composite daily stress score
from physiological and behavioral signals using sigmoid normalization.
"""
from relic.relic_stress_index import main

if __name__ == "__main__":
    main()
