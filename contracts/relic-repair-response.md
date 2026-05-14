# Skill: Relic Repair Response

**Version:** 1.0.0  
**Owner:** relic-core  
**Status:** normative  

## Purpose

Defines the repair workflow for responses that fail validation, safety checks, or quality gates. This skill provides a structured approach to response repair while maintaining safety and privacy guarantees.

## Inputs

- **failed_response**: Response that failed one or more validation checks
- **failure_reasons**: List of specific validation failures
- **repair_context**: Additional context for applying repairs
- **repair_strategy**: Approach to use (minimal_fix, rewrite, escalate)

## Outputs

- **repaired_response**: Response with failures addressed
- **repair_log**: Record of changes made and rationale
- **validation_result**: Confirmation that repairs addressed failures
- **escalation_required**: Whether human review is needed

## Acceptance Checks

- [ ] All identified failures are addressed
- [ ] Repairs do not introduce new failures
- [ ] Safety and privacy guarantees are maintained
- [ ] Repair log provides sufficient audit information
- [ ] Escalation occurs when required

## Privacy Notes

- Repair workflow must not expose raw user data
- Repair log must not contain PII or sensitive context
- User-specific facts must not be persisted
- No user identifiers may be stored in repair artifacts
- User-specific facts must not be stored in skill metadata
- Must not bypass privacy gate
- Must not bypass correction gate

## Block Conditions

- **BLOCKED**: Skill stores user-specific preference
- **BLOCKED**: Skill can promote itself to runtime provider
- **BLOCKED**: Skill candidate promotion is blocked in first iteration
- **BLOCKED**: Repair bypasses correction gate or privacy gate

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-04 | Initial normative specification |
