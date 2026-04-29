"""Cron entrypoint: relic:schemas

Invoked as: python -m relic.schemas
Schedule:   0 5 1 * *

Monthly Early Maladaptive Schema (EMS) detection: identifies active
schemas from accumulated messages using Schema Therapy frameworks.
"""
from mnemon.relic_schemas import main

if __name__ == "__main__":
    main()
