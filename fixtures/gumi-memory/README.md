# Gumi Memory Provider Evaluation Fixtures

Status: fixture directory for PR19.

This directory contains synthetic, redacted fixtures for Hermes-native memory provider evaluation.

## Rules

```text
Do not add real Hermes memory files.
Do not add provider database dumps.
Do not add raw conversation logs.
Do not add API keys, peer cards, or raw profile content.
```

Allowed fixture content:

```text
redacted ExternalMemoryCandidate examples
redacted MemoryExposureEvent examples
provider condition metadata
expected blocker reasons
aggregate counts
```

## Conditions

```text
C0_BUILTIN_ONLY
C1_HOLOGRAPHIC
C2_HINDSIGHT_TOOLS
C3_HINDSIGHT_CONTEXT
C4_BYTEROVER
C5_HONCHO
```

Each condition must be testable without live cloud access. Live providers may be verified separately when available, but core tests must use fixtures or skipped reasons.
