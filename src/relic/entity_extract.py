"""Cron entrypoint: relic:entity-extract

Invoked as: python -m relic.entity_extract
Schedule:   0 4 * * *

Nightly entity extraction from inbox messages: identifies people, places,
and recurring topics and stores them in the entity graph.
"""
from relic.relic_entity_extractor import main

if __name__ == "__main__":
    main()
