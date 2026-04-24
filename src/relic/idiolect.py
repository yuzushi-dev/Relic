"""Cron entrypoint: relic:idiolect

Invoked as: python -m relic.idiolect
Schedule:   0 4 1 * *

Monthly idiolect fingerprint: computes stable linguistic features
(vocabulary richness, syntactic patterns, formulaic expressions).
"""
from relic.relic_idiolect import main

if __name__ == "__main__":
    main()
