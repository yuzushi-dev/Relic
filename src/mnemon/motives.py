"""Cron entrypoint: relic:motives

Invoked as: python -m relic.motives
Schedule:   @manual

On-demand motive analysis: infers implicit and explicit motivational
patterns from accumulated observations and goal data.
"""
from mnemon.relic_motives import main

if __name__ == "__main__":
    main()
