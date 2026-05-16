# UI Validation Fixtures

**Status:** normative  
**Owner:** implementation-worker (PR16A)  
**Purpose:** Provide deterministic fixture data for UI validation tests

## Overview

This directory contains canonical fixture JSON files for validating the researcher UI implementation. All fixtures are:

- Deterministic and reproducible
- Schema-valid (validated against JSON schemas)
- Free of raw private data
- Representative of real-world review scenarios

## Fixture Files

### `input_review_queue.json`

Canonical review queue fixture containing sample items for UI testing:

- S0 items requiring immediate action
- S1 items requiring manual review
- S2 warning items
- Low-risk items for auto-resolution
- Items with various exception flags (disputed, sensitive, stale, uncertain, missing_lineage)

**Privacy Notes:**
- Contains only content hashes, not raw content
- No personal data or raw prompts
- All lineage_refs point to valid artifact IDs

## Validation Commands

```bash
# Validate UI fixtures
make fixture-ui-validation

# Run UI tests
make test-ui
```

## Schema References

- `schemas/researcher_feedback_event.schema.json` - Feedback event schema
- `schemas/feedback_propagation_trace.schema.json` - Propagation trace schema
- `schemas/ui_review_status.schema.json` - Review status schema

## Acceptance Criteria

1. All fixtures parse as valid JSON
2. All fixtures validate against their schemas
3. All fixtures contain required `lineage_refs` and `review_status`
4. S0/S1 items are marked with `can_batch_release: false`
5. All `actor_role` and `target_id` fields are present

---

See [docs/reference/fixtures.md](../../docs/reference/fixtures.md) for the full fixture catalog and how to add new scenarios.
