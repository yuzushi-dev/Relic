# Skill: Relic Model Boundary

**Version:** 1.0.0  
**Owner:** relic-core  
**Status:** normative  

## Purpose

Defines how Relic agents manage boundaries between their capabilities and limitations. This skill ensures agents accurately represent their capabilities, acknowledge uncertainty, and appropriately defer to other systems or human operators.

## Inputs

- **task_request**: The task or query being evaluated
- **agent_capabilities**: Current agent capability profile
- **context_scope**: Available context and tools
- **confidence_threshold**: Minimum confidence required for autonomous response

## Outputs

- **boundary_assessment**: Whether the task falls within agent capabilities
- **confidence_score**: Agent's confidence in handling the request
- **deferral_recommendation**: Whether to defer to human or another system
- **capability_gaps**: Identified limitations relevant to the request

## Acceptance Checks

- [ ] Boundary assessment is accurate and honest
- [ ] Confidence scores reflect actual uncertainty
- [ ] Deferrals are recommended when appropriate
- [ ] Capability gaps are correctly identified
- [ ] Skill candidate promotion is blocked in first iteration

## Privacy Notes

- Boundary assessments must not expose user data
- Capability gap descriptions must not contain PII
- Deferral recommendations must not reveal sensitive context
- User-specific facts must not be stored in skill metadata
- No user-specific facts may be stored in boundary artifacts
- Must not bypass privacy gate
- Must not bypass correction gate

## Block Conditions

- **BLOCKED**: Skill stores user-specific preference
- **BLOCKED**: Skill can promote itself to runtime provider
- **BLOCKED**: Skill candidate promotion is blocked in first iteration
- **BLOCKED**: Agent overstates capabilities to user
- **BLOCKED**: Bypasses privacy gate
- **BLOCKED**: Bypasses correction gate

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-04 | Initial normative specification |
