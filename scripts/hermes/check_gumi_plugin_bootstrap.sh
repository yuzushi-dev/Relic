#!/usr/bin/env bash
# PR22E — verify the Gumi plugin bootstrap is present and redacted.
set -euo pipefail

PROFILE="${HERMES_PROFILE:-default}"
TARGET="${HERMES_HOME:-$HOME/.hermes}/profiles/$PROFILE/plugins/gumi.yaml"

if [ ! -f "$TARGET" ]; then
  echo "MISSING: $TARGET"
  exit 1
fi
if grep -E '(password|api_key|token|secret)' "$TARGET" >/dev/null; then
  echo "FAIL: secrets present in $TARGET"
  exit 2
fi
echo "OK: $TARGET (no secrets)"
