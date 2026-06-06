#!/usr/bin/env bash
# Reapply local hermes-agent patches after a `hermes update` overwrites them.
#
# Usage:
#   HERMES_AGENT_DIR=~/.hermes/hermes-agent ./apply.sh
#
# Patches here capture local modifications to the upstream NousResearch
# hermes-agent that are NOT in the official release. They must be reapplied
# whenever `hermes update` pulls a fresh upstream tree.
#
# Base commit the patches were generated against: a91a57fa5 (v0.14.0, 2026.5.16).
# On a newer upstream the hunks may not apply cleanly — use `git apply --3way`
# and resolve conflicts, then regenerate the patch (see regenerate note below).
set -euo pipefail

HERMES_AGENT_DIR="${HERMES_AGENT_DIR:-$HOME/.hermes/hermes-agent}"
PATCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -d "$HERMES_AGENT_DIR/.git" ]]; then
    echo "ERROR: $HERMES_AGENT_DIR is not a git repo" >&2
    exit 1
fi

cd "$HERMES_AGENT_DIR"

for patch in "$PATCH_DIR"/*.patch; do
    [[ -e "$patch" ]] || continue
    name="$(basename "$patch")"
    if git apply --reverse --check "$patch" >/dev/null 2>&1; then
        echo "SKIP  $name (already applied)"
        continue
    fi
    if git apply --check "$patch" >/dev/null 2>&1; then
        git apply "$patch"
        echo "OK    $name"
    elif git apply --3way "$patch"; then
        echo "OK    $name (3way, verify conflicts)"
    else
        echo "FAIL  $name — apply manually" >&2
    fi
done

echo "Done. Restart gateways:"
echo "  systemctl --user restart hermes-gateway-gumi-daniele.service hermes-gateway-gumi-barbara.service"

# Regenerate after editing the live tree:
#   git -C "$HERMES_AGENT_DIR" diff gateway/run.py > "$PATCH_DIR/gateway-run-py.patch"
