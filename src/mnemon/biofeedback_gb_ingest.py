"""Cron entrypoint: relic:biofeedback-gb-ingest

Invoked as: python -m relic.biofeedback_gb_ingest
Schedule:   @manual

On-demand Gadgetbridge raw file ingest: imports a single Gadgetbridge
JSON export; triggered manually after a device sync.
"""
from mnemon.relic_biofeedback_gb_ingest import main

if __name__ == "__main__":
    main()
