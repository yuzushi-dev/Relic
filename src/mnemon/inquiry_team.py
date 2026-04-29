"""Cron entrypoint: relic:inquiry

Invoked as: python -m relic.inquiry_team
Schedule:   0 4 * * *  (daily at 04:00, after relic:synthesize at 03:00)
Requires:   RELIC_INQUIRY_TEAM=true

Adversarial multi-agent verification of cross-facet hypotheses before
they reach the portrait layer. Blocked hypotheses stay out of PORTRAIT.md.
"""
from mnemon.relic_inquiry_team import main

if __name__ == "__main__":
    main()
