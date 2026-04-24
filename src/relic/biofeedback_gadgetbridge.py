"""Cron entrypoint: relic:biofeedback-gadgetbridge

Invoked as: python -m relic.biofeedback_gadgetbridge
Schedule:   10 4 * * *

Nightly Gadgetbridge data ingestion: imports health data exported
from the Gadgetbridge app (Helio Ring / Amazfit) into the database.
"""
from relic.relic_biofeedback_gadgetbridge import main

if __name__ == "__main__":
    main()
