#!/usr/bin/env bash
# Weekly offline prose-threshold calibration via gemma (Ollama Cloud).
# Generates a timestamped report under ~/.relic/calibration/ and logs the
# suggested DEFAULT_THRESHOLD. Does NOT modify code — a human reviews the
# report and updates DEFAULT_THRESHOLD in prose_critic.py if warranted.
#
# Install (weekly, Monday 04:00):
#   (crontab -l 2>/dev/null; echo "0 4 * * 1 $HOME/Scrivania/relic-oss/scripts/prose_calibration_cron.sh") | crontab -
set -euo pipefail

REPO="${RELIC_REPO:-$HOME/Scrivania/relic-oss}"
OUTDIR="${RELIC_HOME:-$HOME/.relic}/calibration"
mkdir -p "$OUTDIR"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$OUTDIR/prose_calibration_${TS}.json"

cd "$REPO"
python3 scripts/prose_calibration.py --n 60 --output "$OUT" 2>&1 | tee -a "$OUTDIR/cron.log"
echo "[cron] report written: $OUT" | tee -a "$OUTDIR/cron.log"
