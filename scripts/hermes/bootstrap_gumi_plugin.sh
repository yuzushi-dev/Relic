#!/usr/bin/env bash
# PR22E — Hermes-side bootstrap for the Gumi plugin.
# Copies the example config into the active Hermes profile and enables the plugin.
set -euo pipefail

PROFILE="${HERMES_PROFILE:-default}"
PROFILE_DIR="${HERMES_HOME:-$HOME/.hermes}/profiles/$PROFILE"
SRC="$(dirname "$0")/../../configs/hermes/gumi-plugin.example.yaml"

mkdir -p "$PROFILE_DIR/plugins"
cp -n "$SRC" "$PROFILE_DIR/plugins/gumi.yaml"
echo "Gumi plugin example installed at $PROFILE_DIR/plugins/gumi.yaml"
echo "Edit and set 'enabled: true' to activate."
