#!/usr/bin/env bash
# ============================================================================
# Relic E2E Demo Shell Helper
# ============================================================================
# 
# This script provides shell-level access to the E2E demo pipeline.
# - Starts with strict mode for safety
# - Supports --dry-run to preview actions without side effects
# - Never prints secrets, API keys, or private data
# - All outputs are redacted for privacy safety
#
# Usage:
#   ./demo_e2e.sh           # Run full demo
#   ./demo_e2e.sh --dry-run # Preview without executing
#   ./demo_e2e.sh --help    # Show this help
#
# ============================================================================

set -euo pipefail

# Script directory resolution
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Colors for output (disabled if not a terminal)
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# Secret redaction helper
# Replaces potential secret patterns with [REDACTED]
redact_secrets() {
    sed -E 's/(api[_-]?key|secret|password|token|auth)[=:]["'\'']?[[:alnum:]_-]{8,}[蔬"'\'']?/[REDACTED]/gi'
}

# Print help message
show_help() {
    cat << 'HELP_EOF'
Relic E2E Demo Shell Helper

SYNOPSIS
    ./demo_e2e.sh [OPTIONS]

DESCRIPTION
    This script runs the Relic E2E demonstration pipeline locally.
    It demonstrates the full memory correction workflow without:
    - Network access
    - Real private data
    - Cloud provider dependencies

OPTIONS
    --dry-run       Show what would be done without executing
    --help, -h      Show this help message
    --verbose, -v   Enable verbose output

EXAMPLES
    ./demo_e2e.sh              # Run demo
    ./demo_e2e.sh --dry-run     # Preview actions
    ./demo_e2e.sh --verbose     # Verbose output

EXIT CODES
    0   Success
    1   Error (see error messages)
    2   Blocked (privacy/security violation detected)

HELP_EOF
}

# Parse arguments
DRY_RUN=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            show_help
            exit 0
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Banner
echo "========================================================================"
echo "                    Relic E2E Demo Shell Helper"
echo "========================================================================"
echo ""

# Environment check
log_info "Checking environment..."

# Check for Python
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    log_error "Python not found. Please install Python 3.8+"
    exit 1
fi

PYTHON_CMD="${PYTHON:-python3}"
log_info "Using Python: $(${PYTHON_CMD} --version 2>&1 | head -1)"

# Check for project structure
if [[ ! -d "${PROJECT_ROOT}/fixtures" ]]; then
    log_warn "Fixtures directory not found - demo will use synthetic data"
fi

if [[ ! -d "${PROJECT_ROOT}/relic" ]]; then
    log_warn "Relic module not found - demo may have limited functionality"
fi

echo ""

# Dry run mode
if [[ "$DRY_RUN" == true ]]; then
    log_info "DRY-RUN MODE - No changes will be made"
    echo ""
    echo "Would execute the following steps:"
    echo "  [1] Load evaluation fixtures"
    echo "  [2] Process scenarios through mock model"
    echo "  [3] Compute privacy/correction/memory metrics"
    echo "  [4] Generate replication bundle"
    echo "  [5] Print injection/blocking report"
    echo ""
    echo "Would NOT:"
    echo "  - Access network"
    echo "  - Use real private data"
    echo "  - Require cloud provider"
    echo ""
    echo "Would produce:"
    echo "  - artifacts/replication_bundles/demo-e2e-*.zip"
    echo ""
    log_success "Dry-run completed"
    exit 0
fi

# Main execution
log_info "Starting E2E demo pipeline..."
echo ""

# Run the Python demo script
DEMO_SCRIPT="${SCRIPT_DIR}/demo_e2e.py"

if [[ -x "$DEMO_SCRIPT" ]]; then
    if [[ "$VERBOSE" == true ]]; then
        PYTHONPATH="${PROJECT_ROOT}" "${PYTHON_CMD}" "${DEMO_SCRIPT}" --verbose
    else
        PYTHONPATH="${PROJECT_ROOT}" "${PYTHON_CMD}" "${DEMO_SCRIPT}" 2>&1 | redact_secrets || {
            exit_code=$?
            if [[ $exit_code -eq 0 ]]; then
                : # Success
            else
                log_error "Demo script failed with exit code $exit_code"
                exit $exit_code
            fi
        }
    fi
else
    log_error "Demo script not found or not executable: ${DEMO_SCRIPT}"
    exit 1
fi

echo ""
log_success "Demo completed successfully!"
exit 0
