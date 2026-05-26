# Running Evaluations

Relic includes an evaluation framework for measuring Gumi's behavioral quality against defined contracts and rubrics. Evals run on synthetic fixtures and do not require live subjects.

## What evals measure

The currently wired `scripts/eval_run.py` CLI covers:

- **Identity boundary compliance**: does Gumi maintain her diegetic identity under various constraint conditions? Does she collapse into generic assistant, clinical, or mood-tracker behavior?
- **Roleplay admission and PromptContextPack completeness**: does the roleplay fixture suite exercise the expected R1-R10 families?
- **Memory-positive usefulness**: do synthetic MP1-MP8 fixtures produce a passing A5 memory-positive score?
- **Safety signal handling contracts**: are safety signals kept researcher-facing in the fixture-backed tests?

## Running the eval harness

```bash
python scripts/eval_run.py
```

This runs the wired fixture-backed modules against `fixtures/gumi-roleplay/` and `fixtures/memory-positive/`. The output includes release-gate status, aggregate summaries, and scenario counts.

For a specific eval module:

```bash
python scripts/eval_run.py --module gumi_roleplay
python scripts/eval_run.py --module memory_positive
```

Any JSON-producing eval can also write a descriptor-ready report file:

```bash
python scripts/eval_run.py \
  --experiment governance_benchmark \
  --output artifacts/governance-benchmark.json
```

With `--json`, the same JSON is written to stdout and to the `--output` path.
Without `--json`, stdout stays as the short human-readable summary while the
file contains the complete machine-readable report.

For a scientific environment manifest:

```bash
python scripts/eval_run.py \
  --experiment scientific_environment_manifest \
  --output artifacts/scientific-environment-manifest.json \
  --json
```

This emits `scientific_environment_manifest_v1`: a provenance manifest for the
local reproducibility environment. It records the current git branch and commit,
dirty working-tree state, dependency lockfile hashes, discovered container
files, pytest configuration, explicitly ignored tests and reasons, and the
verification commands that must be rerun before a release claim. A dirty working
tree or missing root container definition means the report is not a pinned
release artifact.

To build the root evaluation container from the locked repository context:

```bash
docker build \
  --build-arg RELIC_SOURCE_COMMIT=$(git rev-parse HEAD) \
  --build-arg RELIC_SOURCE_BRANCH=$(git rev-parse --abbrev-ref HEAD) \
  -t relic-scientific-eval:local .
```

The container uses the root `Dockerfile`, `pyproject.toml`, and `uv.lock` to
create a Python/uv evaluation environment. The default command runs the
evidence sufficiency gate, which is expected to remain blocked until the
external evidence artifacts are supplied.

For the single local claim-readiness workflow:

```bash
python scripts/scientific_claim_readiness.py \
  --mode full \
  --output-dir artifacts/scientific-claim-readiness \
  --json
```

This writes `scientific-claim-readiness-run.json`, command logs, the environment
manifest, reproducibility snapshot, mock runtime telemetry artifact, and the
evidence sufficiency gate output. It also writes
`scientific-observation-remediation-audit.json`, which maps the gaps in
`docs/relic_gumi_scientific_observations` to current local evidence and external
blockers. `full` mode also runs compilation,
privacy-marker scan, whitespace diff check, the broad scientific test surface,
generates `scientific-surface-coverage.json` with pytest-cov, and builds the
root Docker image. The coverage file is test-execution evidence for the local
scientific surface; it is not human, live-provider, or deployment evidence. The
command exits non-zero while the evidence sufficiency gate is blocked; that non-zero
exit is expected until the external evidence artifacts are supplied. Use
`--mode smoke` only for a quick artifact exercisability check.

To emit only the observation remediation audit:

```bash
python scripts/eval_run.py --experiment scientific_observation_remediation_audit --json
```

This report has `claim_scope` `observation_gap_to_evidence_traceability`. It is
an audit map, not a success claim: external-evidence gaps remain blocked until
validated live-model, human annotation, expert red-team, longitudinal pilot,
Workbench usability, and runtime telemetry artifacts are supplied.

For the maximum local-only evidence package:

```bash
python scripts/eval_run.py --experiment scientific_local_evidence_package --json
```

This package feeds the evidence sufficiency gate with the controlled
governance benchmark and deterministic mock-gateway runtime telemetry. It should
satisfy those two local requirements while still exiting non-zero because live
provider generation, human annotation, expert red-team, longitudinal pilot, and
Workbench usability evidence remain absent.

For a local reproducibility snapshot:

```bash
python scripts/eval_run.py \
  --experiment scientific_reproducibility_snapshot \
  --output artifacts/scientific-reproducibility-snapshot.json \
  --json
```

This emits `scientific_reproducibility_snapshot_v1`: a hash manifest of the
locally reproducible reports, their reproduction commands, and embedded
expected outputs. It does not include recruited-participant, human-annotation,
expert red-team, live-provider, or production-telemetry evidence.

For the scientific claim-readiness gate:

```bash
python scripts/eval_run.py --experiment scientific_defensibility_gate --json
```

This emits `scientific_defensibility_gate_v1`, a machine-readable gate over the
current evidence set. It is intentionally conservative: without validated
external artifacts for multi-provider live generation, blinded human annotation,
longitudinal pilot results, Workbench usability results, and runtime telemetry,
the command returns exit code `1` and marks broad scientific claims as blocked.

If those artifacts exist as a hash-tracked descriptor, build and validate the
provenance bundle:

```bash
python scripts/eval_run.py \
  --experiment scientific_evidence_bundle \
  --input artifacts/scientific-evidence-descriptor.json \
  --json
```

The descriptor lists artifact file paths for live generation, human annotation,
non-clinical expert red-team results, longitudinal pilot results, Workbench
usability results, and runtime telemetry. The bundle builder records SHA-256,
size, expected report type, expected claim scope, validation flag, and then
embeds the `scientific_defensibility_gate` result. A non-zero exit code means
the embedded gate still blocks broad scientific claims.

The gate requires the imported result artifacts to remain auditably connected
to their validated records, not just to aggregate summaries. Live generation
artifacts must include provider manifests and generation records; annotation
artifacts must include the source packet summary and annotation records;
red-team artifacts must include reviewer manifests and case results; pilot and
Workbench artifacts must include their task/event/result records and completed
qualitative summaries.

For a construct-validity operationalization map:

```bash
python scripts/eval_run.py --experiment construct_operationalization --json
```

This emits `construct_operationalization_v1`, which maps the central RELIC/GUMI
constructs to operational definitions, observable units, positive/negative
examples, annotation dimensions, binary labels, failure types, scoring rules,
acceptance thresholds, and reliability requirements. Its `claim_scope` is
`measurement_construct_operationalization`. It supports protocol clarity and
human-annotation design, but it is not completed human annotation evidence.

You can also pass a preassembled JSON evidence bundle directly to the gate:

```bash
python scripts/eval_run.py \
  --experiment scientific_defensibility_gate \
  --input artifacts/scientific-evidence-bundle.json \
  --json
```

For the controlled governance benchmark:

```bash
python scripts/eval_run.py --experiment governance_benchmark --json
```

This runs `governance_failure_mode_benchmark_v1`, a deterministic synthetic
benchmark over 180 redacted scenarios: 20 failure-mode families with 9 variants
per family. It compares five conditions: `no_memory`, `generic_memory`,
`shared_continuity_only`, `safety_governance_only`, and `full_relic_gumi`. The
report includes a structured scenario manifest, failure rates by
condition/family, paired deltas against baselines, bootstrap confidence
intervals, exact-binomial McNemar summaries for paired binary failures, and
ablation deltas for removing Shared Continuity or safety governance.

The benchmark's `claim_scope` is `synthetic_fixture_controlled`. Treat it as
evidence that the shipped synthetic scenario templates and deterministic
condition responses can exercise specified failure classes. It is not
participant evidence, live-model evidence, clinical validation, or evidence of
longitudinal deployment safety. The no-memory baseline is not forced to fail
safety-only scenarios merely for lacking continuity; this avoids treating a
stateless but otherwise bounded response as a failure when only forbidden-marker
absence is under test.

For a blinded human-annotation packet:

```bash
python scripts/eval_run.py --experiment human_annotation_packet --json
```

This emits `human_annotation_boundary_v1`, an annotation-ready packet sampled
from the controlled benchmark. It includes 80 scenarios and four blinded
responses per scenario: `no_memory`, `generic_memory`,
`shared_continuity_only`, and `full_relic_gumi`. Visible annotation items do not
include condition names; the packet also includes an answer key for later
analysis. The packet contains the ten Likert dimensions and seven binary labels
from the study proposal, plus an analysis plan with percent agreement,
Fleiss kappa, Krippendorff alpha for binary labels, and ICC(2,k) for Likert
ratings.

The annotation packet's `claim_scope` is `annotation_protocol_preparation`. It
does not contain completed human ratings, inter-rater reliability results from
real annotators, or participant outcomes.

To validate imported human-annotation results:

```bash
python scripts/eval_run.py \
  --experiment human_annotation_results \
  --input artifacts/annotation-results.json \
  --json
```

The input JSON must contain `packet` and `annotations`. Annotation records must
stay blinded: they include `annotation_item_id`, `annotator_id`, `likert`, and
`binary`, but no condition labels or answer-key fields. The importer checks item
membership, duplicate annotator/item rows, minimum annotator counts, complete
rubric coverage, valid Likert and binary ranges, and then computes agreement
statistics plus condition summaries after validation.

The results report's `claim_scope` is `imported_human_annotation_results`. It
summarizes caller-supplied ratings; it does not by itself verify recruitment,
annotator qualifications, or that the ratings came from independent humans.
The evidence sufficiency gate also requires complete reliability metrics:
all binary labels need percent agreement of at least `0.80` and Krippendorff
alpha of at least `0.667`, and all Likert dimensions need ICC(2,k) of at least
`0.75`.

For a non-clinical longitudinal pilot protocol:

```bash
python scripts/eval_run.py --experiment longitudinal_pilot_protocol --json
```

Imported longitudinal pilot results must keep the `claim_scope`
`imported_nonclinical_pilot_results` to satisfy the Evidence Sufficiency Gate. Imported Workbench task-study results must use
`imported_workbench_usability_results`.

This emits `longitudinal_nonclinical_pilot_v1`, a machine-readable protocol for
the 2-4 week, 12-24 participant pilot described in the scientific observation
packet. It encodes non-clinical positioning, inclusion and exclusion criteria,
explicit consent gates, participant measures, system event counts, researcher
Workbench tasks, and descriptive feasibility analysis outputs. It also includes
guardrails against therapeutic, diagnostic, crisis, or other high-stakes uses.

The pilot protocol's `claim_scope` is `pilot_protocol_preparation`. It does not
contain participant data, completed feasibility results, or evidence of
longitudinal deployment safety.

To validate imported non-clinical pilot results:

```bash
python scripts/eval_run.py \
  --experiment longitudinal_pilot_results \
  --input artifacts/longitudinal-pilot-results.json \
  --json
```

The input JSON must contain `protocol`, `observed_duration_weeks`,
`participant_records`, `system_event_counts`, `workbench_task_results`, and
`qualitative_summary`. The importer checks the 12-24 participant range, 2-4 week
duration, consent-gate coverage, weekly survey coverage, required system
measures, required Workbench tasks, and excludes raw or clinical outcome fields.

The results report's `claim_scope` is `imported_nonclinical_pilot_results`. It
is descriptive feasibility evidence only; it does not support diagnosis,
treatment, crisis-support, clinical outcome, or causal efficacy claims.
The evidence sufficiency gate also requires progression-style feasibility
signals: completion rate at least `0.80`, withdrawal rate at most `0.20`,
Workbench task success rate at least `0.80`, zero critical errors, and nonzero
system events.

For a live-model generation protocol:

```bash
python scripts/eval_run.py --experiment live_model_generation_protocol --json
```

This emits `live_model_generation_protocol_v1`, a redacted request manifest for
running the controlled governance benchmark against external model providers.
The manifest uses the same synthetic scenario templates and condition labels as
the controlled benchmark, records prompt hashes, stores only redacted prompts,
and specifies provider metadata that must be captured during an actual run.

The protocol's `claim_scope` is `live_generation_protocol_preparation`. It does
not contain completed provider outputs, human annotation, participant data, or
evidence that a provider/model version passed the benchmark. When a provider is
explicitly injected through the Python API, generation records are redacted and
hashed before being returned; public artifacts must not store raw provider
output.

To validate redacted records from an external provider run:

```bash
python scripts/eval_run.py \
  --experiment live_model_generation_artifact \
  --input artifacts/redacted-generation-artifact.json \
  --json
```

The input JSON must contain `protocol`, `provider_manifest`, and
`generation_records`. The importer checks request-manifest membership,
provider/model membership, provider version metadata, prompt-hash consistency,
response-hash format, generation timestamps, duplicate provider/model/request
records, completeness against the protocol, and residual detectable PII in
`redacted_output`. It rejects raw prompt/output fields. Its `claim_scope` is
`redacted_external_generation_records`; it validates and scores caller-supplied
records but does not prove that provider adapters were run correctly unless the
provider-side procedure is separately archived.

For a runtime path coverage inventory:

```bash
python scripts/eval_run.py --experiment runtime_path_coverage --json
```

This emits `runtime_path_coverage_v1`, a machine-readable claims-arguments-
evidence inventory for Hermes/Gumi runtime surfaces. It lists the runtime
invariants that need evidence, path-by-path status, code references, test
references, arguments, and known gaps. Status values distinguish `covered`,
`partial`, `compatibility_surface`, `not_live_default`, and `unresolved`
surfaces so adapter adoption and channel maturity are not overstated.

The inventory includes the SQLite Shared Continuity repository path. That path
is `covered` for repository-level durability: confirmed markers, authoritative
corrections, scope state, and marker lifecycle events are persisted and
reloaded by tests. It also includes the packaged Hermes entry
`transform_llm_output` hook, which is `covered` for contract-level semantic
output review before subject-facing transform output is returned. These are
still not evidence of live Hermes deployment, scheduled off-host recovery, or
multi-week participant retention.

The report's `claim_scope` is `static_contract_inventory`. It is useful for
reviewing whether code and contract tests cover declared runtime boundaries. It
is not live Hermes deployment telemetry, not participant evidence, not clinical
validation, and not proof that every deployed gateway path is active and
configured correctly.

To validate live or mock-gateway runtime telemetry:

```bash
python scripts/eval_run.py \
  --experiment live_runtime_telemetry \
  --input artifacts/runtime-telemetry.json \
  --json
```

The input JSON must contain `deployment_manifest` and `traces`. Each trace must
name a channel and path, include context-request, context-admission or block,
output-review, delivery-decision, and Chronicle/audit events, and keep payloads
redacted. The importer rejects prohibited raw prompt/output fields, detectable
PII in string payloads, malformed hash fields, duplicate trace IDs, channels not
listed in the deployment manifest, and incomplete trace event sets.

The telemetry report's `claim_scope` is `validated_runtime_trace_artifact`. A
mock-gateway artifact is useful runtime-path evidence, but it is not proof of
production channel coverage unless the deployment manifest and capture
procedure identify the production gateway.

The evidence sufficiency gate requires the validated telemetry summary to
include at least two traces, at least two deployment channels, and the required
runtime path IDs `hermes_entry_transform_hook` and `cron_delivery_path`. A
single valid trace or a single isolated path remains blocked because it cannot
support end-to-end runtime coverage claims.

To generate deterministic mock-gateway telemetry from repo code:

```bash
python scripts/eval_run.py --experiment mock_runtime_telemetry_campaign --json
```

To create an artifact file for the evidence-bundle descriptor:

```bash
python scripts/eval_run.py \
  --experiment mock_runtime_telemetry_campaign \
  --output artifacts/mock-runtime-telemetry-campaign.json \
  --json
```

This emits `mock_runtime_telemetry_campaign_v1`, which exercises the current
`OutputCritic` over delivered and blocked synthetic transactions, emits
context, review, delivery, and Chronicle-style events, then validates the
nested `live_runtime_telemetry_v1` report. Its `claim_scope` is
`mock_gateway_runtime_trace_campaign`; it can satisfy the runtime-telemetry gate
as mock evidence, but it is still not production telemetry.

For a synthetic Shared Continuity recovery drill:

```bash
python scripts/eval_run.py --experiment shared_continuity_recovery_drill --json
```

This emits `shared_continuity_recovery_drill_v1`, a repository-level
backup/restore exercise for the SQLite Shared Continuity backend. The drill
creates synthetic subject-scoped continuity markers, backs up the database using
SQLite's backup API, verifies the backup checksum and `PRAGMA integrity_check`,
restores into a new database, and checks restored marker recall and marker-level
events.

The drill's `claim_scope` is `synthetic_repository_recovery_drill`. It is useful
for verifying the mechanics of backup and restore in the repository code. It is
not live Hermes deployment telemetry, not an off-host backup policy, not a
multi-week retention result, and not a production disaster-recovery exercise.

For a synthetic multi-subject isolation/load drill:

```bash
python scripts/eval_run.py --experiment multi_subject_isolation_load --json
```

This emits `multi_subject_isolation_load_v1`, which creates multiple synthetic
subjects through `ContinuityService`, writes subject-confirmed markers through
concurrent SQLite-backed service instances, creates unconfirmed candidates, then
checks subject-scoped marker reads and audit event reads through researcher
assignment groups. The report's `claim_scope` is
`synthetic_multi_subject_researcher_load`. It is useful evidence for local
subject-scope isolation and audit behavior under synthetic load, but it is not
production throughput evidence and does not prove researcher authentication or
authorization controls.

For a synthetic runtime hook/adapter fault-injection drill:

```bash
python scripts/eval_run.py --experiment runtime_fault_injection --json
```

This emits `runtime_fault_injection_v1`, which injects controlled local faults
into hook and adapter surfaces: PromptContextPack builder exception,
pre-triggered fail-safe registry, roleplay L2 side-effect tool without approval,
and Hermes entry startup without subject scope. The expected behavior is
fail-closed or no-injection. The report's `claim_scope` is
`synthetic_hook_adapter_fault_injection`; it is useful for local failure-mode
analysis, but it is not proof that every production adapter is installed or that
network/provider/scheduler failures have been covered.

For a Chronicle audit reconstruction inventory:

```bash
python scripts/eval_run.py --experiment chronicle_audit_coverage --json
```

This emits `chronicle_audit_coverage_v1`, a static matrix of audit questions
that Chronicle is expected to answer. It maps session timelines, model calls,
prompt/response hashes, tool calls, memory reads/writes, profile modifications,
decision evidence, errors/retries, artifact provenance, subject export counts,
deletion dry-runs, and retention-policy counts to code and test evidence. It
also lists Chronicle audit capabilities such as event and decision schemas,
trace joins, subject queries, PROV-O-style provenance, access audit, retention
reaper behavior, export bundles, journal verification/repair, payload hashing,
redaction, and consent-basis fields.

The report's `claim_scope` is `static_query_reconstruction_inventory`. It is
not live runtime telemetry, not a cryptographically signed or Merkle-chained
ledger, and not a completed researcher task study. Use it to inspect what the
repository can reconstruct from structured events; do not cite it as proof that
every deployed runtime emitted complete Chronicle records.

For a researcher Workbench usability protocol:

```bash
python scripts/eval_run.py --experiment workbench_usability_protocol --json
```

This emits `researcher_workbench_usability_v1`, a task-study protocol for
researchers or auditors. It covers finding confirmed continuity markers,
reconstructing follow-up decisions, distinguishing Safety Signals from Shared
Continuity, generating redacted exports, interpreting audit timelines, tracing
correction propagation, checking subject scoping/pause state, and identifying
boundary overreach. The protocol specifies task success, time on task, critical
and noncritical errors, post-task difficulty, SUS, raw NASA-TLX, and
think-aloud notes.

The protocol's `claim_scope` is `usability_protocol_preparation`. It does not
contain completed researcher task results, Workbench usability evidence, or
proof that the fixture-backed Workbench backend is a complete live operational
UI.

To validate imported Workbench usability results:

```bash
python scripts/eval_run.py \
  --experiment workbench_usability_results \
  --input artifacts/workbench-usability-results.json \
  --json
```

The input JSON must contain `protocol`, `participant_summaries`,
`task_results`, and `qualitative_summary`. The importer checks sample-size
bounds, participant summary fields, one result per participant/task pair,
metric ranges, qualitative-analysis completion, and excludes raw notes/exports
or clinical fields. It computes task success, critical error rate, median SUS,
median raw NASA-TLX, and median post-task difficulty against the protocol
thresholds.

The results report's `claim_scope` is `imported_workbench_usability_results`.
It is formative researcher/auditor usability evidence; it does not prove runtime
safety, participant benefit, clinical safety, or production backend completeness.
The evidence sufficiency gate requires the configured Workbench thresholds
to pass, with task success at least `0.80`, median SUS at least `68`, median raw
NASA-TLX at most `50`, median post-task difficulty at most `3`, and no critical
errors.

For a semantic non-clinical boundary check:

```bash
python scripts/eval_run.py --experiment nonclinical_semantic_boundary --json
```

This emits `nonclinical_semantic_boundary_v1`, a synthetic guardrail check for
health-adjacent overreach that is not captured by literal diagnosis-term
blacklists alone. It evaluates whether the delivery-time `OutputCritic` blocks
implicit health inference, professional-bypass language, medication-direction
language, monitoring collapse, and risk-scoring language while still allowing
ordinary non-clinical support and appropriate referral language.

The report's `claim_scope` is `synthetic_semantic_guardrail_check`. It should be
cited only as evidence that a small, explicit semantic boundary suite is wired
to the current output critic and covered runtime transform paths. It is not a
comprehensive medical safety benchmark, not clinical validation, not participant
evidence, and not a substitute for expert-authored red-team cases, live gateway
telemetry, or human annotation.

To validate imported expert red-team boundary results:

```bash
python scripts/eval_run.py \
  --experiment nonclinical_red_team_results \
  --input artifacts/nonclinical-red-team-results.json \
  --json
```

The input JSON must contain `reviewer_manifest` and `cases`. The importer
requires at least 100 cases, at least two independent reviewers, coverage of
health inference, professional bypass, medication direction, monitoring
collapse, risk scoring, and appropriate referral categories, redacted prompt and
output hashes, complete reviewer labels, and no raw or clinical-claim fields.

The results report's `claim_scope` is `imported_expert_red_team_results`. It is
expert boundary-review evidence for tested cases and model outputs only; it is
not clinical validation and does not support diagnostic, therapeutic, or crisis
support claims. The evidence sufficiency gate requires the report summary
to retain full risk-category coverage and at least one unsafe case; total case
count alone is not enough.

## Fixtures

Fixtures are synthetic interaction scenarios stored in `fixtures/`. Each fixture directory contains:
- A README describing the scenario and what it is testing.
- Input data representing a subject profile and interaction sequence.
- Expected output annotations.

Fixtures are versioned. Do not modify them directly in a working branch; create new fixtures for new scenarios.

To list available fixtures:

```bash
python -m relic.eval.fixtures list
```

## Metrics

The core metrics are defined in `relic/eval/metrics.py`. Key metrics for Gumi evaluation:

| Metric | Description |
|---|---|
| `mode_switch_accuracy` | Correct roleplay operational mode selected |
| `relational_dose` | Appropriate level of relational presence for context |
| `dependency_boundary_trigger_rate` | Correct activation of dependency warnings |
| `disclosure_when_reality_challenged` | Correct handling of questions about Gumi's nature |
| `roleplay_suppression_correctness` | Correct suppression of persona in high-stakes contexts |
| `persona_intrusion_cost` | Penalty for persona elements appearing in non-roleplay contexts |
| `clinicalization_rate` | Frequency of forbidden clinical terms in output |

## Ablation studies

The controlled governance benchmark exposes two fixture-backed ablations:

- `without_shared_continuity`: compares `full_relic_gumi` to `safety_governance_only`.
- `without_safety_governance`: compares `full_relic_gumi` to `shared_continuity_only`.

Lower-level ablation helpers also exist under `relic/eval/ablation.py` for
Python API use.

## Baselines

The controlled governance benchmark exposes release-independent comparison
conditions through `--experiment governance_benchmark`. Memory-positive A0/A2/A5
baseline helpers remain available under `relic/eval/baselines.py` and are used
by the memory-positive module tests.

## Replication bundles in eval

Replication bundles are built through `relic.eval.replication_bundle` and `relic.replication.bundle`. `scripts/eval_run.py` does not currently expose `--output-bundle`.

See [Artifact Lifecycle](../architecture/artifact-lifecycle.md) for more on replication bundles.

## Debug bundles

For failed cases, a debug bundle can be produced showing the full pipeline trace:

```bash
python -m relic.eval.debug_bundle --case-id <case_id> --output ./debug/
```

Debug bundles are large and should not be committed to the repository.
