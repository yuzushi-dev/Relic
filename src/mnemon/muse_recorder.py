"""Cron entrypoint: relic:muse-recorder

Invoked as: python -m relic.muse_recorder
Schedule:   @manual

On-demand Muse 2 EEG session recorder: captures and stores a single
EEG session; triggered manually when a recording session starts.
"""
from mnemon.relic_muse_recorder import main

if __name__ == "__main__":
    main()
