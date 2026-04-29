"""Cron entrypoint: relic:biofeedback-correlation

Invoked as: python -m relic.biofeedback_correlation
Schedule:   15 4 * * *

Nightly biofeedback↔personality correlation analysis.
Runs after biofeedback ingestion (04:05/04:10) to compute Spearman
correlations between physiological signals and text-derived facet observations,
then sends a structured report via Telegram.
"""
from mnemon.relic_biofeedback_correlation import main

if __name__ == "__main__":
    main()
