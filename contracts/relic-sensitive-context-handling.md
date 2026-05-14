# Skill: Relic Sensitive Context Handling

**Version:** 1.0.0  
**Owner:** relic-core  
**Status:** normative  

## Purpose

Defines how Relic agents handle sensitive or privileged context. This skill ensures that sensitive information is properly redacted, scoped, and protected throughout the agent workflow.

## Inputs

- **context_input**: Raw context that may contain sensitive information
- **sensitivity_level**: Classification of context sensitivity (public, internal, confidential, restricted)
- **processing_type**: Type of processing to perform (analysis, storage, transmission)

## Outputs

- **processed_context**: Context with appropriate redactions applied
- **sensitivity_tag**: Classification of the processed output
- **redaction_log**: Record of what was redacted and why
- **access_scope**: Defined scope for who can access the output

## Acceptance Checks

- [ ] PII is identified and redacted before output
- [ ] Sensitivity tags accurately reflect content classification
- [ ] Redaction log provides audit trail without exposing redacted content
- [ ] Access scope is appropriately restricted
- [ ] User-specific facts are never stored in skill metadata

## Privacy Notes

- **CRITICAL**: No raw PII may appear in processed output
- **CRITICAL**: Redaction must be validated before transmission
- **CRITICAL**: Access scope must follow least-privilege principle
- **CRITICAL**: User preferences and facts must not be persisted
- No user identifiers may be stored in processing artifacts
- User-specific facts must not be stored in skill metadata
- Must not bypass privacy gate
- Must not bypass correction gate

## Block Conditions

- **BLOCKED**: Skill stores user-specific preference
- **BLOCKED**: Skill can promote itself to runtime provider
- **BLOCKED**: Skill candidate promotion is blocked in first iteration
- **BLOCKED**: Context bypasses privacy gate
- **BLOCKED**: Bypasses correction gate

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-05-04 | Initial normative specification |
