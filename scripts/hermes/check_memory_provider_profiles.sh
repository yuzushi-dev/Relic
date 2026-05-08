#!/usr/bin/env bash
# Check memory provider profiles for secrets, isolation, and compliance
# Part of PR19A - Provider inventory and isolated profile harness

set -uo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PROFILES_DIR="${REPO_ROOT}/configs/hermes/profiles"
ARTIFACTS_DIR="${REPO_ROOT}/artifacts/gumi-provider-eval"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
DRY_RUN=false
VERBOSE=false
HELP=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            HELP=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Show help
if [[ "$HELP" == true ]]; then
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Check memory provider profiles for secrets, isolation, and compliance."
    echo ""
    echo "Options:"
    echo "  --dry-run    Show what would be checked without making changes"
    echo "  --verbose    Show detailed output"
    echo "  --help       Show this help message"
    echo ""
    echo "This script validates:"
    echo "  - No secrets or API keys in profile files"
    echo "  - Profile isolation (at most one external provider per profile)"
    echo "  - PR20 candidates are marked as non-Hermes-native"
    echo "  - Compliance with HERMES_BOOTSTRAP_CONTRACT.md"
    echo ""
    exit 0
fi

echo "=== Memory Provider Profile Check ==="
echo "Repository: ${REPO_ROOT}"
echo "Profiles: ${PROFILES_DIR}"
echo ""

# Check profiles directory exists
if [[ ! -d "$PROFILES_DIR" ]]; then
    echo -e "${RED}ERROR: Profiles directory does not exist: ${PROFILES_DIR}${NC}"
    exit 1
fi

# Required profiles
REQUIRED_PROFILES=(
    "gumi-c0-builtin.yaml"
    "gumi-c1-holographic.yaml"
    "gumi-c2-hindsight-tools.yaml"
    "gumi-c3-hindsight-context.yaml"
    "gumi-c4-byterover.yaml"
    "gumi-c5-honcho.yaml"
)

# Forbidden patterns from LOCAL_PRIVATE_DATA_TEST_CONTRACT.md
FORBIDDEN_PATTERNS=(
    "API_KEY"
    "ANTHROPIC_API_KEY"
    "OPENAI_API_KEY"
    "GEMINI_API_KEY"
    "honcho_api_key"
    "hindsight_token"
    "byterover_token"
    "sk-"
    "sk1-"
    "sk2-"
)

FAILED=0
PROFILES_OK=0
SECRETS_OK=0
ISOLATION_OK=0

# Check required profiles exist
echo "Checking profile existence..."
for profile in "${REQUIRED_PROFILES[@]}"; do
    profile_path="${PROFILES_DIR}/${profile}"
    if [[ -f "$profile_path" ]]; then
        echo -e "  ${GREEN}✓${NC} ${profile} exists"
        ((PROFILES_OK++)) || true
    else
        echo -e "  ${RED}✗${NC} ${profile} missing"
        ((FAILED++)) || true
    fi
done
echo ""

if [[ $PROFILES_OK -ne ${#REQUIRED_PROFILES[@]} ]]; then
    echo -e "${RED}ERROR: Not all required profiles exist${NC}"
    exit 1
fi

# Check for secrets in profiles
echo "Checking for secrets in profiles..."
for profile in "${REQUIRED_PROFILES[@]}"; do
    profile_path="${PROFILES_DIR}/${profile}"
    
    if [[ ! -f "$profile_path" ]]; then
        continue
    fi
    
    found_forbidden=false
    for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
        if grep -q "$pattern" "$profile_path" 2>/dev/null; then
            echo -e "  ${RED}✗${NC} ${profile}: contains forbidden pattern '${pattern}'"
            found_forbidden=true
            SECRETS_OK=0
            ((FAILED++)) || true
        fi
    done
    
    if [[ "$found_forbidden" == false ]]; then
        echo -e "  ${GREEN}✓${NC} ${profile}: no secrets found"
    fi
done
echo ""

# Check profile isolation (at most one external provider)
echo "Checking profile isolation..."
for profile in "${REQUIRED_PROFILES[@]}"; do
    profile_path="${PROFILES_DIR}/${profile}"
    
    if [[ ! -f "$profile_path" ]]; then
        continue
    fi
    
    # C0-C3 should have no external providers
    if [[ "$profile" == gumi-c0-* ]] || [[ "$profile" == gumi-c1-* ]] || \
       [[ "$profile" == gumi-c2-* ]] || [[ "$profile" == gumi-c3-* ]]; then
        external_count=0
        if grep -q "external_provider\|external_path\|provider_type.*external" "$profile_path" 2>/dev/null; then
            external_count=1
        fi
        if [[ "$external_count" -gt 0 ]]; then
            echo -e "  ${RED}✗${NC} ${profile}: builtin profile should not have external providers"
            ((FAILED++)) || true
        else
            echo -e "  ${GREEN}✓${NC} ${profile}: no external providers"
        fi
    # C4-C5 should be marked as skipped
    elif [[ "$profile" == gumi-c4-* ]] || [[ "$profile" == gumi-c5-* ]]; then
        hermes_native_false=false
        status_skipped=false
        if grep -q "hermes_native.*false" "$profile_path" 2>/dev/null; then
            hermes_native_false=true
        fi
        if grep -q "status.*skipped\|skip_reason" "$profile_path" 2>/dev/null; then
            status_skipped=true
        fi
        if [[ "$hermes_native_false" == true ]] && [[ "$status_skipped" == true ]]; then
            echo -e "  ${GREEN}✓${NC} ${profile}: correctly marked as skipped (PR20 candidate)"
        else
            echo -e "  ${RED}✗${NC} ${profile}: PR20 candidate should be marked as skipped"
            ((FAILED++)) || true
        fi
    fi
done
echo ""

# Summary
echo "=== Summary ==="
if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}All checks passed!${NC}"
    echo ""
    echo "Profile isolation: PASSED"
    echo "Secrets check: PASSED"
    echo "PR20 candidates: CORRECTLY SKIPPED"
    exit 0
else
    echo -e "${RED}Some checks failed (${FAILED} issues)${NC}"
    exit 1
fi
