#!/usr/bin/env bash
# PR22H — dry-run installer for Gumi continuity cron.
set -euo pipefail
SRC="$(dirname "$0")/../../configs/hermes/cron/gumi-continuity.example.yaml"
echo "Would install cron from $SRC (dry-run, no side effects)."
cat "$SRC"
