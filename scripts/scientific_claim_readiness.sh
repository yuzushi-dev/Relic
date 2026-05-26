#!/usr/bin/env sh
set -eu

PYTHON="${PYTHON:-python3}"
exec "$PYTHON" scripts/scientific_claim_readiness.py "$@"
