# Skill: Relic Correction Workflow

**Version:** 1.0.0  
**Owner:** relic-core  
**Status:** normative  

## Purpose

Defines the workflow for correcting agent errors, hallucinations, or policy violations. This skill ensures corrections are applied consistently, verified, and documented without introducing new errors.

## Inputs

- **error_type**: Classification of the error (hallucination, policy_violation, fact_error, style_error)
- **original_response**: The response containing the error
- **correction_context**: Information needed to apply the correction
- **severity**: Impact level of the error (critical, high, medium, low)

## Outputs

- **corrected_response**: The fixed version of the response
- **correction_rationale**: Explanation of why the correction was made
- **verification_result**: Confirmation that the correction was applied correctly
- **escalation_flag**: Whether the error requires human review

## Acceptance Checks

- [ ] Corrections are factually accurate and verifiable
- [ ] Original error context is preserved for audit
- [ ] Correction does not introduce new errors or policy violations
- [ ] Escalation is triggered for critical severity issues
- [ ] Skill candidate promotion is blocked in first iteration

## Privacy Notes

- Correction workflow must not expose raw user data
- Rationale must not contain PII or sensitive context
- Audit trail must not persist user-specific facts
- No user identifiers may be stored in correction artifacts
- User-specific facts must not be stored in skill metadata
- Must not bypass privacy gate

## Block Conditions

- **BLOCKED**: Skill stores user-specific preference
- **BLOCKED**: Skill can promote itself to runtime provider
- **BLOCKED**: Skill candidate promotion is blocked in first iteration
- **BLOCKED**: Correction bypasses privacy gate
- **BLOCKED**: Correction bypasses correction gate

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-04 | Initial normative specification |
