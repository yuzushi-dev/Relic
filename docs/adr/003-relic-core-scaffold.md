# ADR: Relic Core Scaffold Decision

Date: 2026-04-19
Status: Accepted

## Context

The migration work requires a public `relic_core` package boundary, but the starting branch did not contain a first-class implementation package. The current `relic` package still mixes scientific logic, runtime-oriented utilities, and Hermes-facing entrypoints.

## Decision

Adopt the new `src/relic_core` package as the canonical extraction target.

## Rationale

- It gives the migration a stable namespace that does not imply Hermes ownership.
- It allows gradual extraction via compatibility re-exports before deeper refactors.
- It avoids mutating the private downstream `workspace-gumi` assumptions during the first pass.

## Alternatives Considered

- Retain a compatibility layer only: rejected because it leaves no clear target boundary.
- Discard and replace later: rejected because it postpones the namespace decision and blocks interface work.

## Consequences

- First-pass files in `relic_core` may re-export from `relic.*`.
- Subsequent refactors should move implementation inward module by module.
- Wrapper deletion in `relic.*` remains blocked until import-graph evidence says otherwise.

