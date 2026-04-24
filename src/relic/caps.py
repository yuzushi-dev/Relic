"""Cron entrypoint: relic:caps

Invoked as: python -m relic.caps
Schedule:   30 5 2 * *

Monthly CAPS synthesis: extracts if-then behavioral signatures
from session and message data using the CAPS personality framework.
"""
from relic.relic_caps import main

if __name__ == "__main__":
    main()
