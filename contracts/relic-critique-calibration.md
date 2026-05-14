# Skill: Relic Critique Calibration

**Version:** 1.0.0  
**Owner:** relic-core  
**Status:** normative  

## Purpose

Defines how Relic agents perform self-critique and calibration of responses. This skill provides a structured approach to evaluating response quality, identifying errors, and improving output accuracy.

## Inputs

- **query**: The original user query or task
- **response**: The initial agent response to evaluate
- **context**: Relevant context for evaluation (optional)
- **calibration_type**: Type of calibration to perform (accuracy, completeness, tone, safety)

## Outputs

- **critique_result**: Structured evaluation of the response
- **calibration_score**: Numeric or categorical quality assessment
- **improvement_suggestions**: Actionable recommendations for improvement
- **confidence_level**: Agent's confidence in the calibration assessment

## Acceptance Checks

- [ ] Critique is grounded in verifiable criteria
- [ ] Calibration score reflects actual quality, not self-serving bias
- [ ] Suggestions are specific and actionable
- [ ] Confidence level accurately represents certainty

## Privacy Notes

- Critique must not expose raw user data in evaluation output
- Calibration feedback must not contain PII or sensitive context
- Skill metadata must not store user-specific preferences or facts
- No user identifiers may be persisted in critique artifacts
- User-specific facts must not be stored in skill metadata
- Must not bypass privacy gate

## Block Conditions

- **BLOCKED**: Skill stores user-specific preference
- **BLOCKED**: Skill can promote itself to runtime provider
- **BLOCKED**: Skill candidate promotion is blocked in first iteration
- **BLOCKED**: Critique bypasses privacy gate
- **BLOCKED**: Bypasses correction gate

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-04 | Initial normative specification |
