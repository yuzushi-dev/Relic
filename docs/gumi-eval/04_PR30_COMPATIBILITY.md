# PR30 Transform/No_Agent Compatibility Checks

## Overview

This document verifies that Gumi maintains diegetic voice when Hermes v0.13 hooks (PR30 transform/no_agent) fire. These checks ensure that PR30 mechanisms do not introduce clinical terms, agent personas, or identity collapse patterns.

## PR30 Hook Descriptions

### transform_llm_output Hook

The `transform_llm_output` hook fires on every LLM output before it is returned to the subject. This hook must not introduce clinical terminology or diagnostic language into Gumi's output.

**Compatibility Requirement**: Gumi's diegetic voice remains relational and non-clinical after hook processing.

### no_agent Cron

The `no_agent` cron executes on a schedule when the agent is in a passive/reflective mode. This cron must not create an agent-like persona in Gumi output.

**Compatibility Requirement**: Gumi maintains diegetic frame without adopting agentic characteristics.

## Compatibility Test Cases

### Transform Hook Cases

1. **Clinical Term Injection**: Verify transform hook does not inject clinical terms (e.g., "anxiety disorder", "symptoms", "patient")
2. **Diagnostic Framing**: Verify transform hook does not add diagnostic framing to emotional content
3. **Therapeutic Positioning**: Verify transform hook does not position Gumi as therapeutic

### no_agent Cron Cases

1. **Agent Persona Creation**: Verify no_agent cron does not create agent-like persona markers
2. **Diegetic Frame Maintenance**: Verify Gumi remains in diegetic frame without agentic references
3. **Relational Continuity**: Verify relational continuity is maintained without agent dependencies

## Block Conditions

The following conditions block PR30 compatibility:

- `BLOCKED_VOICE_COLLAPSE_UNDER_TRANSFORM`: Gumi voice must not collapse under transform hook
- `BLOCKED_CLINICAL_TERM_FROM_HOOK`: Clinical terms must not be introduced by hook
- `BLOCKED_AGENT_PERSONA_FROM_NO_AGENT_CRON`: Agent persona must not be created by no_agent cron
- `BLOCKED_PR30_HOOK_CAUSES_IDENTITY_COLLAPSE`: PR30 hooks must not cause identity collapse

## Test Fixtures

Test cases are defined in `fixtures/gumi-eval/pr30_transform_compatibility_cases.json`.
