#!/usr/bin/env bash
set -euo pipefail

TASK_ID="${1:?task id required}"
TASK_PACKET="${2:?task packet path required}"
SANDBOX="${3:-workspace-write}"
PROFILE="${CODEX_PROFILE:-ollama-minimax-m27}"

if [[ ! -f "$TASK_PACKET" ]]; then
  echo "BLOCKED_MISSING_TASK_PACKET: $TASK_PACKET" >&2
  exit 2
fi

OUT_DIR=".codex/runs/$TASK_ID"
mkdir -p "$OUT_DIR"

codex exec \
  --profile "$PROFILE" \
  --sandbox "$SANDBOX" \
  --json \
  --output-last-message "$OUT_DIR/final.md" \
  - \
  < "$TASK_PACKET" \
  > "$OUT_DIR/events.jsonl" \
  2> "$OUT_DIR/stderr.log"

echo "$OUT_DIR/final.md"
