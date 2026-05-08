# Replication Package

Status: normative documentation for PR15.

## Purpose

Defines the structure, schemas, and contracts for Relic replication bundles. Replication bundles enable independent verification of Relic behavior without exposing private user data, raw prompts, or sealed local artifacts.

## Reproducibility Classes

### Exact Reproducibility

All inputs, random seeds, and execution paths are deterministic and committed to source control. Any agent with the same codebase, fixtures, and environment can reproduce identical outputs.

### Semantic Reproducibility

The system produces equivalent outputs for equivalent inputs but may vary due to:
- Non-deterministic model responses (provider-level variance)
- Time-dependent behavior (cron scheduling)
- Floating-point arithmetic across platforms

Semantic reproducibility requires fixtures and expected outputs to be committed. Variance must be documented in the privacy exclusion report.

### Statistical Reproducibility

Aggregated metrics (e.g., privacy leakage rate, correction obedience rate) are reproducible across runs but individual decisions may vary. Requires statistical significance reporting.

## Bundle Contents

### Required Files

| File | Purpose | Privacy Status |
|------|---------|----------------|
| `run_manifest.json` | Execution metadata, reproducibility class, evidence IDs | Public |
| `artifact_checksums.json` | SHA-256 hashes of all compiled artifacts | Public |
| `environment.txt` | Pinned dependency versions | Public |
| `policy_snapshot.yaml` | Compiler policy at execution time | Public |
| `schema_versions.json` | Relic schema versions used | Public |
| `seed_config.json` | Random seed configuration | Public |
| `fixtures/` | Deterministic input fixtures | Public |
| `expected_outputs/` | Expected output fixtures | Public |

### Conditional Files

| File | Purpose | Privacy Status |
|------|---------|----------------|
| `cac_trace.jsonl` | CAC decision trace (redacted) | Public |
| `privacy_trace.jsonl` | Privacy gate decisions (redacted) | Public |
| `correction_trace.jsonl` | Correction propagation (redacted) | Public |
| `eval_results.json` | Evaluation metrics | Public |
| `report.md` | Human-readable findings | Public |

### UI Validation Artifacts (when PR16 present)

| File | Purpose | Privacy Status |
|------|---------|----------------|
| `researcher_feedback_trace.jsonl` | Feedback event log | Public |
| `feedback_propagation_trace.jsonl` | Artifact stale-marking trace | Public |
| `ui_audit_log.jsonl` | UI interaction audit | Public |
| `ui_validation_report.md` | Validation findings | Public |
| `artifact_diff_after_feedback.json` | Diff of artifacts post-feedback | Public |

### Excluded from Public Bundles

- Raw private prompts
- Raw provider store contents
- `MEMORY.md`, `USER.md`, diary files
- Sealed local replay payloads
- API keys or tokens
- Raw final prompt logs

## Literature Positioning

Replication methodology follows:

- **ACM Artifact Review and Badging** (2023) for reproducibility tiers
- **ML Reproducibility Checklist** (NeurIPS 2020) for experiment reproducibility
- **FAIR Principles** (Wilkinson et al. 2016) for data findability and accessibility

Evidence levels:

| Level | Description | Badge |
|-------|-------------|-------|
| S0 | Not reproducible | - |
| S1 | Benchmark adaptation with documented changes | Available |
| S2 | Private observational with redacted traces | Available |
| S3 | Participant study with anonymized traces | Available with restrictions |

## Debug Bundles

Debug bundles are **separate** from public replication bundles. See `DEBUG_BUNDLE.md` for the debug bundle contract.

## Acceptance Checks

- [ ] All required public files are present
- [ ] No raw private data in bundle contents
- [ ] Run manifest declares reproducibility class
- [ ] Artifact checksums can be verified from clean checkout
- [ ] Policy snapshot is included
- [ ] Debug bundle is documented separately
- [ ] Sealed local replay is excluded from public bundles
- [ ] Privacy exclusion report documents all omissions
