"""Cron entrypoint: relic:domain-prober

Invoked as: python -m relic.domain_prober
Schedule:   @manual

On-demand domain probe: generates a targeted question for a specific
life domain to fill coverage gaps in the personality model.
"""
from relic.relic_domain_prober import main

if __name__ == "__main__":
    main()
