# Contract Tests

Relic has a set of behavioral contracts defined in `contracts/`. These specify what the system must and must not do in specific scenarios. Contract tests verify that the code meets these specifications.

## The contracts

| Contract | File | What it governs |
|---|---|---|
| Model boundary | `contracts/relic-model-boundary.md` | How agents represent their capabilities and acknowledge uncertainty |
| Correction workflow | `contracts/relic-correction-workflow.md` | How errors are corrected, documented, and escalated |
| Critique calibration | `contracts/relic-critique-calibration.md` | How the post-turn critic evaluates outputs |
| Repair response | `contracts/relic-repair-response.md` | How the system recovers from plugin or pipeline failures |
| Sensitive context handling | `contracts/relic-sensitive-context-handling.md` | How sensitive patterns are handled without clinical language |

Each contract specifies inputs, outputs, acceptance checks, and privacy requirements.

## How contracts are tested

Contract tests live alongside domain tests in `tests/`. They are identified by the fact that they test boundary conditions explicitly: what gets blocked, what gets passed, what gets escalated.

Key contract test files:

| Test file | What it tests |
|---|---|
| `tests/ui/test_no_direct_artifact_write.py` | Researcher UI cannot write directly to artifacts |
| `tests/ui/test_subject_correction_supremacy.py` | Subject corrections override inferred values |
| `tests/shared-continuity/test_continuity_clinicalization_guard.py` | Forbidden clinical terms cannot appear in continuity |
| `tests/shared-continuity/test_normative_protocol.py` | Continuity markers meet the normative protocol |
| `tests/safety/test_escalation_notifier.py` | Safety signals trigger correct escalation behavior |
| `tests/profile/test_inferred_fields_not_directly_injected.py` | Inferred fields stay out of direct runtime injection |
| `tests/profile/test_inferred_fields_do_not_use_clinical_terms.py` | Inferred fields use non-clinical language |
| `tests/ui/test_no_cross_subject_event_leakage.py` | Events cannot cross subject boundaries |

## Adding contract tests

When you add a new feature that touches a boundary (privacy, correction, clinical language, subject scope), add a contract test that:

1. Demonstrates the happy path: the system does what it should.
2. Demonstrates the failure path: the system correctly blocks what it should block.

Name the test file `test_<specific_boundary>.py` and place it in the appropriate subdirectory. Document what contract or invariant it verifies in the module docstring.

## Privacy requirements in contracts

Every contract has a section specifying privacy requirements. The common ones:

- Audit trails must not persist user-specific facts beyond what is needed for the audit.
- Rationale fields must not contain PII.
- Skill metadata must not store user-specific facts.
- No component may bypass the privacy gate.

If your contribution touches any component that produces audit output, rationale text, or metadata, verify it meets these requirements.
