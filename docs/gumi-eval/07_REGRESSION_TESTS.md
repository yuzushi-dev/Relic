# Gumi Identity Regression Tests

## Overview

Regression tests ensure all prior PR28 checks pass as a complete suite. These tests verify no collapse patterns reappear and all cross-PR checks (PR30, PR32, PR33) continue to pass.

## Regression Suite Categories

### 1. Collapse Scenario Tests
Tests that all identity collapse scenarios pass - no generic assistant, clinical assistant, mood tracker, or backend disclosure collapse.

### 2. Cross-PR Compatibility Tests
Tests that PR30 hooks, PR32 governance, and PR33 continuity do not cause regression.

### 3. Acceptance Gate Tests
Automated gates that block deployment if any collapse pattern is detected.

## Running the Regression Suite

```bash
python -m pytest tests/gumi-eval/test_gumi_identity_regression.py -v
python -m pytest tests/gumi-eval/test_acceptance_gates.py -v
python -m pytest tests/gumi-eval/ -v --tb=short
```

## Success Criteria

- All collapse scenario tests pass
- All cross-PR compatibility tests pass
- Acceptance gates block on any collapse detection
- Suite is deterministic and reproducible
