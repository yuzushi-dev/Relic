# Hermes v0.13 Rollout and Rollback Plan

## Overview

This document describes the rollout phases and rollback procedures for all Hermes v0.13 features.

## Rollback Principles

1. Every new feature must have a corresponding rollback flag
2. Rollback flags are stored in policy snapshots, NOT runtime state
3. Setting a rollback flag to `false` must completely disable the feature
4. Phase 0 and Phase 1 changes must NOT affect live behavior

## Phase 0: Read-Only Discovery (No Live Behavior Change)

Phase 0 involves read-only discovery and analysis. No live behavior changes occur.

### Features in Phase 0
- none identified yet

### Rollback for Phase 0
- No rollback needed as no changes are made

## Phase 1: Documentation, Schemas, Fixtures, Contract Tests (No Live Behavior Change)

Phase 1 creates documentation, schemas, fixtures, and contract tests. No live behavior changes occur.

### Features in Phase 1

| Feature | Rollback Flag | Rollback Procedure | Verification Steps |
|---------|--------------|-------------------|-------------------|
| no_agent_cron_mode | `hermes_no_agent_cron_mode_enabled` | Set to `false` in policy snapshot | Verify cron jobs stop creating no_agent sessions |
| transform_llm_output_hook | `hermes_transform_llm_output_enabled` | Set to `false` in policy snapshot | Verify LLM output flows without transformation |
| X-Hermes-Session-Key | `hermes_session_key_enabled` | Set to `false` in policy snapshot | Verify session keys not required |
| Platform Allowlists | `hermes_platform_allowlist_enabled` | Set to `false` in policy snapshot | Verify all platforms allowed by default |
| Checkpoints and Auto-Resume | `hermes_checkpoint_enabled` | Set to `false` in policy snapshot | Verify sessions resume without checkpoints |

### Rollback for Phase 1
- No live behavior change - all changes are documentation and schema definitions
- If schema validation fails, do not proceed to Phase 2

## Phase 2: Implementation (Affects Live Behavior)

Phase 2 involves actual implementation. Live behavior changes occur.

### Features in Phase 2

| Feature | Rollback Flag | Rollback Procedure | Verification Steps |
|---------|--------------|-------------------|-------------------|
| no_agent_cron_mode | `hermes_no_agent_cron_mode_enabled` | Set to `false`, restart Hermes | Cron jobs create standard sessions |
| transform_llm_output_hook | `hermes_transform_llm_output_enabled` | Set to `false`, restart Hermes | LLM output returned without transformation |
| X-Hermes-Session-Key | `hermes_session_key_enabled` | Set to `false`, restart Hermes | Sessions work without session key header |
| Platform Allowlists | `hermes_platform_allowlist_enabled` | Set to `false`, restart Hermes | All platforms allowed by default |
| Checkpoints and Auto-Resume | `hermes_checkpoint_enabled` | Set to `false`, restart Hermes | Sessions resume without checkpoint check |

## General Rollback Procedure

1. **Immediate** - Set rollback flag to `false` in policy snapshot
2. **Restart** - Restart Hermes service to apply flag change
3. **Verify** - Run verification steps for affected feature
4. **Monitor** - Monitor for any residual issues

## Block Conditions

The following conditions will block rollout:

- `BLOCKED_NEW_BEHAVIOR_WITHOUT_ROLLBACK` - Feature without rollback flag
- `BLOCKED_PHASE_0_LIVE_BEHAVIOR_CHANGE` - Phase 0 attempting live changes
- `BLOCKED_PHASE_1_LIVE_BEHAVIOR_CHANGE` - Phase 1 attempting live changes
- `BLOCKED_ROLLBACK_FLAG_IN_RUNTIME_STATE` - Rollback flag stored in runtime
- `BLOCKED_ROLLBACK_DOES_NOT_DISABLE_FEATURE` - Rollback flag doesn't fully disable feature

## Contract Validation

All features must pass contract tests before proceeding to next phase:

- PR30A: `test_no_agent_cron_mode_contract.py` - 5 tests
- PR30B: `test_transform_llm_output_hook_contract.py` - 6 tests
- PR30C: `test_session_key_contract.py` - 5 tests
- PR30D: `test_platform_allowlist_contract.py` - 5 tests
- PR30E: `test_checkpoint_contract.py` - 5 tests
- PR30F: `test_rollback_flag_contract.py` - 6 tests

Total: 32 contract tests must pass before Phase 2 deployment.