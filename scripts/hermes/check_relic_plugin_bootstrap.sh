#!/usr/bin/env bash
#===============================================================================
# check_relic_plugin_bootstrap.sh - Relic Plugin Bootstrap Verification
#
# This script verifies the Relic Hermes plugin can be bootstrapped without
# requiring live Hermes credentials or external dependencies.
#
# Usage:
#   ./check_relic_plugin_bootstrap.sh [--dry-run] [--config <path>] [--help]
#
# Exit codes:
#   0 - Bootstrap verification passed
#   1 - Bootstrap verification failed
#   2 - Invalid arguments
#===============================================================================

set -euo pipefail

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Default values
DRY_RUN=false
CONFIG_PATH=""
VERBOSE=false

# Colors (only if terminal supports it)
if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    NC=''
fi

#-------------------------------------------------------------------------------
# Helper functions
#-------------------------------------------------------------------------------

log_info() {
    echo "[INFO] $*"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $*" >&2
}

print_usage() {
    cat << USAGE
Usage: $(basename "$0") [OPTIONS]

Verify Relic Hermes plugin bootstrap without live credentials.

Options:
  --dry-run      Run in dry-run mode (no live credential checks)
  --config PATH  Path to plugin configuration file
  --verbose      Enable verbose output
  --help         Show this help message

Exit codes:
  0 - Bootstrap verification passed
  1 - Bootstrap verification failed
  2 - Invalid arguments
USAGE
}

#-------------------------------------------------------------------------------
# Argument parsing
#-------------------------------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --config)
            CONFIG_PATH="$2"
            shift 2
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            print_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            print_usage
            exit 2
            ;;
    esac
done

#-------------------------------------------------------------------------------
# Verification functions
#-------------------------------------------------------------------------------

check_python_module() {
    local module="$1"
    local description="${2:-Python module check}"
    
    if python3 -c "import ${module}" 2>/dev/null; then
        log_success "$description"
        return 0
    else
        log_error "$description"
        return 1
    fi
}

check_file_exists() {
    local file="$1"
    local description="${2:-File check}"
    
    if [[ -f "$file" ]]; then
        log_success "$description"
        return 0
    else
        log_error "$description: $file not found"
        return 1
    fi
}

check_directory_exists() {
    local dir="$1"
    local description="${2:-Directory check}"
    
    if [[ -d "$dir" ]]; then
        log_success "$description"
        return 0
    else
        log_error "$description: $dir not found"
        return 1
    fi
}

verify_no_secrets_in_file() {
    local file="$1"
    local description="${2:-Secret check}"
    
    # Check for common secret patterns (REDACTED patterns are OK)
    # Exclude patterns with REDACTED, placeholder markers, or example/sample text
    local secret_found=false
    while IFS= read -r line; do
        if [[ "$line" =~ (REDACTED|placeholder|example|sample) ]]; then
            continue
        fi
        secret_found=true
        break
    done < <(grep -E '(sk-[a-zA-Z0-9]{20,}|api_key\s*=|token\s*=\s*"[^"]+")' "$file" 2>/dev/null || true)
    
    if [[ "$secret_found" == "true" ]]; then
        log_error "$description: Potential secrets found"
        return 1
    fi
    
    log_success "$description"
    return 0
}

#-------------------------------------------------------------------------------
# Main verification logic
#-------------------------------------------------------------------------------

main() {
    local exit_code=0
    
    echo "=============================================="
    echo " Relic Hermes Plugin Bootstrap Verification"
    echo "=============================================="
    echo ""
    
    # Dry-run mode banner
    if [[ "$DRY_RUN" == true ]]; then
        log_info "Running in DRY-RUN mode (no live credential checks)"
        echo ""
    fi
    
    #----------------------------------------------------------------------------
    # Phase 1: File structure verification
    #----------------------------------------------------------------------------
    echo "Phase 1: File Structure"
    echo "----------------------------------------------"
    
    local plugin_dir="${REPO_ROOT}/relic/hermes_plugin"
    check_directory_exists "$plugin_dir" "Plugin directory exists" || exit_code=1
    
    # Check required Python modules
    for module in "plugin" "commands" "hooks" "fail_safe" "tool_permissions"; do
        check_file_exists "${plugin_dir}/${module}.py" "Module ${module}.py exists" || exit_code=1
    done
    
    echo ""
    
    #----------------------------------------------------------------------------
    # Phase 2: Configuration verification
    #----------------------------------------------------------------------------
    echo "Phase 2: Configuration"
    echo "----------------------------------------------"
    
    local config_file="${REPO_ROOT}/configs/hermes/relic-plugin.example.yaml"
    if [[ -n "$CONFIG_PATH" ]]; then
        config_file="$CONFIG_PATH"
    fi
    
    if [[ -f "$config_file" ]]; then
        check_file_exists "$config_file" "Configuration file exists"
        verify_no_secrets_in_file "$config_file" "Configuration has no secrets" || exit_code=1
    else
        log_warning "Configuration file not found: $config_file"
        log_info "Using default configuration"
    fi
    
    # Check TOOL_PERMISSION_MATRIX.md
    local matrix_file="${REPO_ROOT}/TOOL_PERMISSION_MATRIX.md"
    check_file_exists "$matrix_file" "Tool permission matrix exists" || exit_code=1
    
    echo ""
    
    #----------------------------------------------------------------------------
    # Phase 3: Python import verification
    #----------------------------------------------------------------------------
    echo "Phase 3: Python Import Verification"
    echo "----------------------------------------------"
    
    if [[ "$DRY_RUN" == true ]]; then
        log_info "Skipping Python import checks in dry-run mode"
    else
        # Change to repo root for Python path
        cd "$REPO_ROOT"
        
        # Check core dependencies
        check_python_module "relic.hermes_plugin" "Relic plugin module imports" || exit_code=1
        check_python_module "relic.control.pause" "Pause controller imports" || exit_code=1
        check_python_module "relic.cac" "CAC module imports" || exit_code=1
    fi
    
    echo ""
    
    #----------------------------------------------------------------------------
    # Phase 4: Test verification
    #----------------------------------------------------------------------------
    echo "Phase 4: Test Verification"
    echo "----------------------------------------------"
    
    local test_dir="${REPO_ROOT}/tests/hermes_plugin"
    check_directory_exists "$test_dir" "Test directory exists" || exit_code=1
    
    # Count test files
    local test_count
    test_count=$(find "$test_dir" -name "test_*.py" 2>/dev/null | wc -l)
    if [[ "$test_count" -gt 0 ]]; then
        log_success "Found $test_count test files"
    else
        log_warning "No test files found"
    fi
    
    echo ""
    
    #----------------------------------------------------------------------------
    # Phase 5: Bootstrap script verification
    #----------------------------------------------------------------------------
    echo "Phase 5: Bootstrap Script"
    echo "----------------------------------------------"
    
    local bootstrap_script="${SCRIPT_DIR}/check_relic_plugin_bootstrap.sh"
    check_file_exists "$bootstrap_script" "Bootstrap script exists" || exit_code=1
    
    # Verify script has strict mode
    if head -n 5 "$bootstrap_script" | grep -q "set -"; then
        log_success "Script has strict mode"
    else
        log_error "Script missing strict mode"
        exit_code=1
    fi
    
    # Verify script supports dry-run
    if grep -q "dry-run\|dry_run\|DRY_RUN" "$bootstrap_script"; then
        log_success "Script supports dry-run mode"
    else
        log_error "Script missing dry-run support"
        exit_code=1
    fi
    
    # Verify no hardcoded secrets
    if grep -E 'sk-[a-zA-Z0-9]{20,}' "$bootstrap_script" 2>/dev/null | grep -v -E '(REDACTED|example|sample)'; then
        log_error "Script contains hardcoded secrets"
        exit_code=1
    else
        log_success "Script has no hardcoded secrets"
    fi
    
    echo ""
    
    #----------------------------------------------------------------------------
    # Summary
    #----------------------------------------------------------------------------
    echo "=============================================="
    echo " Verification Summary"
    echo "=============================================="
    
    if [[ $exit_code -eq 0 ]]; then
        log_success "All bootstrap checks passed!"
        echo ""
        if [[ "$DRY_RUN" == true ]]; then
            log_info "Dry-run completed successfully. No live credentials were checked."
        fi
        exit 0
    else
        log_error "Some bootstrap checks failed"
        echo ""
        log_info "Review errors above and ensure all required files exist."
        exit 1
    fi
}

# Run main
main
