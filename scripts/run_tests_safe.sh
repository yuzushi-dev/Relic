#!/usr/bin/env bash
# Guarded sequential test runner for low-memory machines.
#
# Why: `pytest tests/` keeps all ~3300 tests in ONE process for the whole run.
# Leaked resources (open SQLite handles, threads, spawned `python -m relic`
# subprocesses with no per-test timeout) accumulate until RAM/CPU saturate and
# the whole desktop freezes. Collection itself is cheap (~100 MB); the danger is
# the long-lived single process.
#
# This script runs ONE directory per pytest process (resources freed between
# dirs) and wraps each run in:
#   - systemd-run --user --scope cgroup cap  -> kernel kills only this scope if
#     it balloons, never the desktop;
#   - timeout                                -> kills a hung subprocess test;
#   - nice/ionice                            -> OS stays responsive under load.
#
# Usage:
#   scripts/run_tests_safe.sh                # all dirs
#   scripts/run_tests_safe.sh tests/cli ...  # specific targets
# Env overrides: MEM_MAX, SWAP_MAX, PER_DIR_TIMEOUT
set -u

MEM_MAX="${MEM_MAX:-4G}"           # hard RAM cap per pytest process
SWAP_MAX="${SWAP_MAX:-1G}"         # swap cap per pytest process
PER_DIR_TIMEOUT="${PER_DIR_TIMEOUT:-300}"  # wall-clock seconds per dir
PYTEST_ARGS="-q -p no:cacheprovider -p no:warnings --tb=line"

cd "$(dirname "$0")/.." || exit 1

have_systemd_run() { command -v systemd-run >/dev/null 2>&1 && systemd-run --user --scope -q -p MemoryMax=64M true >/dev/null 2>&1; }
USE_CGROUP=0
have_systemd_run && USE_CGROUP=1

run_one() {
  local target="$1"
  local cmd=(python3 -m pytest "$target" $PYTEST_ARGS)
  local guarded=(timeout -k 10 "$PER_DIR_TIMEOUT" nice -n 19 ionice -c3 "${cmd[@]}")
  if [ "$USE_CGROUP" -eq 1 ]; then
    systemd-run --user --scope -q \
      -p MemoryMax="$MEM_MAX" -p MemorySwapMax="$SWAP_MAX" \
      -- "${guarded[@]}"
  else
    "${guarded[@]}"
  fi
  local rc=$?
  case $rc in
    0)   echo "[$target] OK" ;;
    124) echo "[$target] TIMEOUT (killed at ${PER_DIR_TIMEOUT}s)" ;;
    137) echo "[$target] KILLED (memory cap ${MEM_MAX} hit — cgroup OOM)" ;;
    *)   echo "[$target] FAIL (rc=$rc)" ;;
  esac
  return $rc
}

if [ "$#" -gt 0 ]; then
  targets=("$@")
else
  # One target per directory; root-level test_*.py files run as a final batch.
  mapfile -t targets < <(find tests -maxdepth 1 -mindepth 1 -type d ! -name '__pycache__' | sort)
  targets+=("tests/test_smoke.py tests/test_config.py tests/test_db_schema.py tests/test_cli_setup.py tests/test_makefile_targets.py")
fi

echo "cgroup cap: $([ $USE_CGROUP -eq 1 ] && echo "on (MemoryMax=$MEM_MAX)" || echo off) | per-dir timeout: ${PER_DIR_TIMEOUT}s"
fails=()
for t in "${targets[@]}"; do
  run_one "$t" || fails+=("$t")
done

echo "---"
if [ "${#fails[@]}" -eq 0 ]; then
  echo "ALL GREEN"
else
  printf 'FAILED/TIMED-OUT: %s\n' "${fails[@]}"
  exit 1
fi
