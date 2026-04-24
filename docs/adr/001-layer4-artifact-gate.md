# ADR 001 - Layer 4 Artifact Gate

Status: Accepted
Date: 2026-04-16

## Context

The Relic architecture separates evidence acquisition, trait estimation,
specialist analyses, and downstream artifacts into four layers (whitepaper
§3, §5.3). The bootstrap hook was designed to inject only `PORTRAIT.md`
into agent sessions, leaving every other artifact -- Layer 2 traits dumps,
Layer 3 specialist outputs (schemas, defenses, CAPS, appraisal, attachment,
idiolect, LIWC, stress), and the inspection-only `PROFILE.md` -- off the
conversational surface.

Before this ADR, that rule lived only as a hardcoded string literal
(`${dataDir}/PORTRAIT.md`) inside `hooks/relic-bootstrap/handler.ts`.
A contributor who later added a second artifact injector -- for debugging,
for demo purposes, or because a specialist module produced a rich Markdown
output -- would not encounter any structural friction. The whitepaper's
§10 "Sixth" implication (higher-order layers require stricter governance)
was therefore enforced by convention only.

## Decision

Introduce an explicit whitelist in `hooks/shared/artifact-gate.ts`:

    export const INJECTABLE_ARTIFACTS = ["PORTRAIT.md"];
    export function isInjectableArtifact(filename: string): boolean { ... }

Every bootstrap-adjacent hook that resolves a filesystem artifact for
injection must invoke `isInjectableArtifact(basename)` before reading the
file. Adding an entry to `INJECTABLE_ARTIFACTS` is the governance moment:
a reviewer sees a single-line diff to a named constant instead of a new
path literal buried in handler code.

Source-level tests in `tests/test_artifact_gate.py` enforce:

- the gate module and its exports exist,
- the whitelist equals `["PORTRAIT.md"]` exactly,
- the bootstrap handler imports and calls the predicate before `readFile`,
- a parametric blocklist (Layer 3 JSON outputs + `PROFILE.md`) is not
  silently added to the whitelist.

## Alternatives considered

1. **Directory-based convention** (e.g. only files under
   `runtime/relic/public/` are injectable). Rejected: relies on
   filesystem layout rather than a reviewable list, and requires a
   second migration step whenever the data directory is restructured.
2. **Runtime manifest** (YAML describing each artifact's access level).
   Rejected as over-engineering for the current scope: one whitelist
   string is enough, and the cost of a second entry is small.
3. **Keeping the convention unwritten**. Rejected: the concern in
   whitepaper §10 is precisely that convention decays under contributor
   churn.

## Consequences

- Adding a new injectable artifact becomes a deliberate PR touching
  both the whitelist and this ADR.
- Layer 3 outputs can still be produced, stored, and inspected through
  other channels; the gate only governs bootstrap injection.
- The whitepaper claim that PORTRAIT.md is the sole bootstrap artifact
  is now enforced structurally rather than by documentation.
