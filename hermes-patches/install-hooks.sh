#!/usr/bin/env bash
# Install git hooks in the hermes-agent repo so a git-based `hermes update`
# (pull / checkout / rebase) auto-reapplies the local patches.
#
# Git hooks live in .git/hooks (not version-controlled), so rerun this if the
# hermes-agent repo is ever re-cloned. The systemd ExecStartPre drop-in is the
# primary mechanism; these hooks are belt-and-suspenders for update-without-restart.
#
# Usage:
#   HERMES_AGENT_DIR=~/.hermes/hermes-agent ./install-hooks.sh
set -euo pipefail

HERMES_AGENT_DIR="${HERMES_AGENT_DIR:-$HOME/.hermes/hermes-agent}"
PATCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPLY="$PATCH_DIR/apply.sh"
HOOKDIR="$HERMES_AGENT_DIR/.git/hooks"

[[ -d "$HOOKDIR" ]] || { echo "ERROR: $HOOKDIR not found" >&2; exit 1; }

for h in post-merge post-checkout post-rewrite; do
    cat > "$HOOKDIR/$h" <<EOF
#!/usr/bin/env bash
# Reapply local relic patches after a git-based 'hermes update'.
# Managed by relic-oss/hermes-patches. Safe + idempotent.
exec "$APPLY"
EOF
    chmod +x "$HOOKDIR/$h"
    echo "installed $h"
done
