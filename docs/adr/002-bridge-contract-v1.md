# ADR: Bridge Contract V1

Date: 2026-04-19
Status: Accepted

## Context

Relic artifacts must cross from the scientific core into a live companion/runtime layer without leaking raw DB state or private relational memory. The current runtime already enforces a narrow `PORTRAIT.md` bootstrap surface in Hermes-era hooks. The migration needs the same boundary stated independently of Hermes.

## Decision

Version `v1` of the bridge contract allows only `PORTRAIT.md` to cross the default downstream subject-artifact boundary.

## Allowed Artifacts

- `PORTRAIT.md`

## Forbidden Artifacts

- raw SQLite DB access
- `PROFILE.md`
- layer 2 trait dumps
- layer 3 specialist outputs
- private Gumi state files

## Enforcement

- enforcement must happen at the core or adapter publication boundary, not only in prompt text
- downstream consumers must pin the contract version they expect

## Observability

- every published artifact should log artifact name, contract version, and destination
- contract mismatches should fail loudly

## Rollback

- if a non-whitelisted artifact is about to cross the boundary, publication must abort and leave the live runtime unchanged

