# Scientific Defensibility Literature Check

Date: 2026-05-24

This note records the external literature checked before adding the controlled
governance benchmark. It is intentionally scoped to experiment design and claim
discipline, not promotional positioning.

## Verified Sources

- Park et al., 2023, "Generative Agents: Interactive Simulacra of Human Behavior"  
  https://arxiv.org/abs/2304.03442
- Packer et al., 2023, "MemGPT: Towards LLMs as Operating Systems"  
  https://arxiv.org/abs/2310.08560
- Maharana et al., 2024, "Evaluating Very Long-Term Conversational Memory of LLM Agents" / LoCoMo  
  https://arxiv.org/abs/2402.17753
- Xu et al., 2025, "A-MEM: Agentic Memory for LLM Agents"  
  https://arxiv.org/abs/2502.12110
- Kapoor et al., 2024, "AI Agents That Matter"  
  https://arxiv.org/abs/2407.01502
- Bickmore and Picard, 2005, "Establishing and Maintaining Long-Term Human-Computer Relationships"  
  https://doi.org/10.1145/1067860.1067867
- Kay and Kummerfeld, 2012, "Creating personalized systems that people can scrutinize and control"  
  https://doi.org/10.1145/2395123.2395129
- Nahum-Shani et al., 2018, JITAI design principles  
  https://pmc.ncbi.nlm.nih.gov/articles/PMC5364076/
- Wang et al., 2024, "Judging the Judges: A Systematic Study of Position Bias in LLM-as-a-Judge"  
  https://arxiv.org/abs/2406.07791
- Inter-rater reliability references supporting percent agreement,
  chance-corrected agreement, and conservative interpretation thresholds for
  annotation studies.  
  https://pmc.ncbi.nlm.nih.gov/articles/PMC3900052/  
  https://pmc.ncbi.nlm.nih.gov/articles/PMC3402032/  
  https://direct.mit.edu/coli/article/50/3/817/120233/Analyzing-Dataset-Annotation-Quality-Management-in
- Live and reproducible LLM/agent benchmark literature emphasizing fresh
  benchmark material, released evaluation outputs, contamination controls,
  model/version metadata, and reproducible harnesses.  
  https://www.lmsys.org/blog/2024-04-19-arena-hard/  
  https://openreview.net/forum?id=sKYHBTAxVa  
  https://aclanthology.org/2024.emnlp-main.764.pdf
- Privacy-preserving LLM request and redaction literature supporting prompt and
  output minimization/redaction before model calls or public artifact release.  
  https://arxiv.org/abs/2604.12064  
  https://pubmed.ncbi.nlm.nih.gov/41988159/
- World Health Organization, 2024, "Ethics and governance of artificial intelligence for health: guidance on large multi-modal models"  
  https://www.who.int/publications/b/70584
- U.S. FDA, "Clinical Decision Support Software" guidance and FAQ  
  https://www.fda.gov/medical-devices/software-medical-device-samd/clinical-decision-support-software-frequently-asked-questions-faqs
- Cheng et al., 2024, "Don't be my Doctor! Recognizing Healthcare Advice in
  Large Language Models"  
  https://aclanthology.org/2024.emnlp-industry.72/
- Physician-led red-teaming work on unsafe answers to patient-posed medical
  questions, including the HealthAdvice dataset and model-response evaluations.  
  https://pmc.ncbi.nlm.nih.gov/articles/PMC13013898/  
  https://github.com/rachellea/LLMPatientSafety
- Expert and clinician review/red-team approaches for health-adjacent AI
  outputs support separating automated guardrail checks from expert-labeled
  unsafe-advice evidence before making boundary claims.  
  https://pmc.ncbi.nlm.nih.gov/articles/PMC13013898/  
  https://aclanthology.org/2024.emnlp-industry.72/
- Assurance case / safety case literature on structured claims, arguments,
  evidence, and traceability from high-level objectives to design, code, and
  tests.  
  https://www.sciencedirect.com/topics/computer-science/assurance-case  
  https://www.sciencedirect.com/science/article/pii/S0925753513001021
- Static architecture conformance checking literature, including Reflexion
  Model-style comparison between intended architecture and implementation.  
  https://www.cs.cmu.edu/~mabianto/papers/CMU-ISR-08-132.pdf
- Recent AI assurance and auditability work emphasizing machine-readable
  evidence, traceability, enforcement semantics, and runtime evidence rather
  than policy-only claims.  
  https://www.nist.gov/itl/ai-risk-management-framework  
  https://arxiv.org/abs/2604.13767  
  https://arxiv.org/abs/2603.18096  
  https://overt.is/
- Trace-based testing and synthetic transaction monitoring literature supports
  using runtime traces as test assertions in CI while keeping synthetic monitor
  evidence separate from production telemetry claims.  
  https://docs.tracetest.io/  
  https://opentelemetry.io/blog/2023/testing-otel-demo/
- Reproducible artifact and provenance-bundle literature emphasizing
  self-contained evidence packages, claim-by-claim reproduction instructions,
  hash manifests, workflow provenance, FAIR metadata, and Research Object
  Crate-style workflow run records.  
  https://www.nist.gov/programs-projects/scientific-workflow  
  https://www.acm.org/publications/policies/artifact-review-and-badging-current  
  https://www.researchobject.org/ro-crate/about_ro_crate  
  https://pmc.ncbi.nlm.nih.gov/articles/PMC8760356/  
  https://pmc.ncbi.nlm.nih.gov/articles/PMC11386446/  
  https://2026.splashcon.org/track/splash-2026-artifact-evaluation  
  https://www.sigops.org/2023/artifact-evaluation-theory-and-practice/  
  https://aaai.org/conference/aaai/aaai-23/reproducibility-checklist/
- Guardrail benchmarking and runtime-guardrail architecture literature
  supporting explicit input/output filter evaluation and multi-layer runtime
  controls instead of relying only on model alignment or prompt instructions.  
  https://aclanthology.org/2024.emnlp-main.1022/  
  https://arxiv.org/abs/2408.02205
- Audit-trail and provenance literature emphasizing chronological records,
  reconstruction of events, governance rationales, provenance interchange, and
  traceable records for accountability.  
  https://arxiv.org/abs/2601.20727  
  https://www.w3.org/TR/prov-o/  
  https://cdn.governance.ai/Toward-Trustworthy-AI-Development.pdf
- Persistent-memory and event-sourcing/observability literature supporting
  durable state outside the context window, structured memory records, and
  event-level reconstruction rather than relying on in-process dictionaries or
  untraceable prompt history.  
  https://arxiv.org/abs/2310.08560  
  https://arxiv.org/abs/2402.17753  
  https://arxiv.org/abs/2603.19935  
  https://www.sciencedirect.com/science/article/pii/S0164121221001126
- SQLite and contingency-planning references supporting consistent database
  snapshots, explicit integrity verification, and tested restore procedures
  rather than treating an untested file copy as recovery evidence.  
  https://www.sqlite.org/backup.html  
  https://www.sqlite.org/pragma.html#pragma_integrity_check  
  https://www.sqlite.org/wal.html  
  https://csrc.nist.gov/pubs/sp/800/34/r1/upd1/final
- HCI and usability literature supporting representative task studies with task
  success, time on task, critical errors, subjective usability/workload, and
  think-aloud notes.  
  https://pmc.ncbi.nlm.nih.gov/articles/PMC4713903/  
  https://pmc.ncbi.nlm.nih.gov/articles/PMC4532606/  
  https://pmc.ncbi.nlm.nih.gov/articles/PMC7506540/  
  https://www.tandfonline.com/doi/abs/10.1080/10447318.2014.904177

## Implications For RELIC/GUMI

- Agent-memory systems such as MemGPT, LoCoMo, and A-MEM make recall,
  context management, and long-term conversational memory the immediate
  comparison class. RELIC/GUMI experiments therefore need baseline and ablation
  conditions, not only architecture tests.
- The agent-evaluation literature warns that benchmark-only evidence can be
  brittle and overfit. The new benchmark labels its claim as
  `synthetic_fixture_controlled` and reports limitations directly in JSON.
- Relational-agent and scrutable-user-modeling literature makes human
  perception, contestability, correction, and longitudinal relationship quality
  relevant constructs. The current benchmark does not claim those outcomes; it
  only covers controlled failure-mode fixtures.
- Health-adjacent AI governance and FDA CDS boundaries support keeping
  clinical, diagnostic, and therapeutic claims out of the artifact. The benchmark
  reports "no clinical efficacy claim" as a first-class limitation.
- Health-advice recognition and medical-safety work supports treating
  pseudo-clinical behavior as a semantic boundary problem, not only a forbidden
  term problem. RELIC/GUMI therefore needs tests that catch indirect health
  inference, professional-bypass language, medication direction, monitoring
  collapse, and risk scoring even when no literal diagnosis label appears.
- Health-adjacent red-team literature supports requiring external expert review
  for borderline and unsafe-advice cases. A small synthetic output-critic suite
  is useful wiring evidence, but defensibility needs an imported expert
  red-team artifact with independent reviewer labels and risk-category coverage.
- LLM-as-judge bias literature supports avoiding unsupported judge claims in
  this first remediation step. The benchmark uses deterministic marker scoring
  plus paired statistics; future LLM/human judging must include bias controls,
  frozen prompts, calibration, and inter-rater reliability.
- Inter-rater reliability literature supports treating reliability as a gate
  condition, not just a reported appendix. RELIC/GUMI therefore requires
  complete reliability coverage for all annotation labels/dimensions, minimum
  binary percent agreement of 0.80, minimum binary Krippendorff alpha of 0.667,
  and minimum Likert ICC(2,k) of 0.75 before the human-annotation requirement
  can satisfy the claim-readiness gate.
- Live benchmark and evaluation-harness literature supports releasing enough
  redacted prompt/output evidence for reproducibility while capturing provider,
  model, version, and sampling metadata. RELIC/GUMI therefore needs a
  live-model generation protocol before any claim that the governance benchmark
  works with real model outputs.
- Privacy-preserving LLM request literature supports minimizing and redacting
  prompts/outputs before external provider use and public artifact release. The
  live-generation protocol therefore hashes prompts/responses, redacts PII, and
  refuses to store raw provider output in public records.
- Human annotation reliability literature supports reporting both raw agreement
  and chance-corrected agreement. The annotation packet therefore plans percent
  agreement, Fleiss kappa, Krippendorff alpha for binary labels, and ICC(2,k)
  for Likert dimensions instead of treating a single mean rating as sufficient.
- Feasibility-pilot, SUS, trust-in-automation, and EMA/micro-EMA literature
  supports treating the longitudinal pilot as feasibility, acceptability,
  usability, trust calibration, and burden evidence. It should not be framed as
  clinical efficacy, treatment effect, or proof of deployment safety.
- Assurance-case and architecture-conformance literature supports representing
  runtime defensibility as claim-scoped evidence, not as a single broad
  "safe/unsafe" assertion. The runtime coverage artifact therefore records
  invariants, paths, arguments, code evidence, test evidence, and explicit gaps.
- AI auditability and machine-readable evidence literature supports emitting
  structured JSON reports with enforcement semantics and limitations. The
  runtime coverage report uses `static_contract_inventory` and refuses to claim
  live deployment telemetry or global runtime proof.
- Trace-based testing literature supports mock-gateway synthetic transactions
  as runtime-path evidence when they emit events that can be asserted. The
  remediation therefore adds a deterministic mock telemetry campaign that
  exercises repo code and validates its own nested runtime telemetry report,
  while still refusing to treat it as production channel evidence.
- Reproducible artifact and provenance-bundle literature supports packaging
  evidence with hash manifests and explicit claim mappings. RELIC/GUMI
  therefore needs a scientific evidence bundle that records artifact file
  hashes, report identities, validation status, and the claim-readiness gate
  result instead of relying on loose JSON files.
- Runtime-guardrail literature supports checking guardrails at the actual
  execution path where outputs leave the model boundary. The remediation
  therefore verifies the semantic non-clinical boundary at both the direct Gumi
  critic and the packaged Hermes entry transform hook, while still requiring
  live gateway telemetry before claiming deployment-wide coverage.
- Audit-trail and provenance literature supports testing the concrete questions
  an auditor or researcher can reconstruct. The Chronicle coverage artifact
  therefore maps query questions to event/decision/snapshot/provenance records
  and names the absence of cryptographic ledger evidence as a limitation.
- HCI usability literature supports evaluating the Researcher Workbench through
  representative task success, task time, error rates, perceived difficulty,
  SUS, workload, and think-aloud notes. The Workbench artifact therefore
  prepares a task-study protocol rather than claiming completed usability
  evidence.
- Persistent-memory literature supports treating longitudinal continuity as a
  storage and retrieval problem, not only prompt context management. The
  remediation therefore adds a SQLite-backed Shared Continuity repository and
  marker-level lifecycle events, while still refusing to claim multi-week field
  durability without backup/restore and live deployment drills.
- SQLite backup and contingency-planning guidance supports making recovery a
  tested drill with a consistent snapshot, checksum, integrity check, and
  restore verification. The new recovery artifact therefore tests backup and
  restore mechanics but does not claim off-host scheduling, production recovery
  objectives, or multi-week retention.

## Implemented In This Branch

- `relic/eval/controlled_benchmark.py` implements
  `governance_failure_mode_benchmark_v1`.
- `scripts/eval_run.py --experiment governance_benchmark --json` exposes the
  benchmark through the eval CLI.
- `tests/eval/test_controlled_governance_benchmark.py` verifies required
  conditions, 150-300 scenario coverage, balanced family counts, structured
  scenario manifests, paired deltas, bootstrap intervals, exact-binomial
  McNemar summaries, and exact reproducibility metadata.
- `relic/eval/scientific_defensibility.py` implements
  `scientific_defensibility_gate_v1`, a conservative claim-readiness gate that
  blocks broad scientific claims unless required external evidence artifacts are
  present and valid.
- `scripts/eval_run.py --experiment scientific_defensibility_gate --json`
  emits that gate through the eval CLI and returns a non-zero exit code when
  required evidence is missing.
- `relic/eval/scientific_evidence_bundle.py` implements
  `scientific_evidence_bundle_v1`, a provenance-tracked evidence bundle builder
  that hashes required artifact files, checks expected report identities and
  claim scopes plus validation flags, embeds the assembled evidence bundle, and
  runs the scientific defensibility gate.
- `scripts/eval_run.py --experiment scientific_evidence_bundle --input
  <descriptor.json> --json` validates a descriptor-driven evidence bundle
  through the eval CLI. JSON-producing evals can write the same machine-readable
  report to `--output`, including while stdout remains a compact text summary,
  so generated reports can be referenced by descriptor paths and hashed.
- `relic/eval/scientific_environment_manifest.py` implements
  `scientific_environment_manifest_v1`, a local environment provenance manifest
  for reproducibility claims. It records git branch/commit and dirty state,
  hashes dependency files such as `pyproject.toml` and `uv.lock`, inventories
  discovered container definitions, captures pytest configuration and explicit
  test exclusions with reasons, and lists required verification commands.
- `scripts/eval_run.py --experiment scientific_environment_manifest --output
  <manifest.json> --json` emits that manifest through the eval CLI. The manifest
  marks a dirty working tree or missing root container definition as not ready
  for a pinned release artifact; it is reproducibility provenance, not external
  scientific evidence.
- A root `Dockerfile` now defines a Python 3.12.3 / pinned-uv evaluation
  container that installs from `uv.lock`; `.dockerignore` records the build
  context exclusions. The manifest includes the corresponding `docker build`
  command so the containerized environment is part of the reproducibility
  checklist. This addresses the local environment artifact gap, but it still
  does not satisfy recruited-participant, live-model, expert-review, usability,
  or telemetry requirements.
- `scripts/scientific_claim_readiness.py` and
  `scripts/scientific_claim_readiness.sh` implement the single local
  claim-readiness workflow requested by the reproducibility gap. The workflow
  generates the environment manifest, reproducibility snapshot, mock telemetry
  artifact, scientific defensibility gate output, command logs, and a
  `scientific_claim_readiness_run_v1` execution report; in full mode it also
  runs compile/privacy/diff checks, the broad scientific test surface with a
  pytest-cov JSON coverage artifact, and the Docker build. A blocked gate is
  treated as an expected non-zero outcome, not as fabricated scientific success.
  The coverage artifact addresses the reproducibility checklist gap for local
  test execution reporting, but it is not evidence for human perception,
  live-provider robustness, or production runtime behavior.
- `relic/eval/scientific_observation_remediation_audit.py` implements
  `scientific_observation_remediation_audit_v1`, a claim/evidence/gap map from
  the observation packet to current repo artifacts. It separates
  locally-resolved rows, partially-resolved rows, intentionally scoped-out rows,
  and rows still blocked on external evidence. This follows the TEVV/assurance
  case discipline of keeping claims connected to evidence and limitations rather
  than allowing summary reports to imply unsupported scientific readiness.
- `relic/eval/scientific_local_evidence_package.py` implements
  `scientific_local_evidence_package_v1`, the maximum claim-readiness package
  that can be assembled without external human/provider/deployment data. It
  feeds the controlled governance benchmark and mock-gateway runtime telemetry
  into `scientific_defensibility_gate_v1`, satisfying the local benchmark and
  runtime-telemetry requirements while preserving the five external-evidence
  blockers.
- `relic/eval/scientific_reproducibility_snapshot.py` implements
  `scientific_reproducibility_snapshot_v1`, a local reproducibility snapshot
  that embeds currently reproducible fixture/protocol/mock reports, records
  canonical JSON hashes, and lists exact `scripts/eval_run.py --output`
  commands for regenerating each report. It explicitly records zero external
  evidence artifacts and does not satisfy the claim-readiness gate by itself.
- `scripts/eval_run.py --experiment scientific_reproducibility_snapshot
  --output <snapshot.json> --json` emits that snapshot through the eval CLI.
- `relic/eval/human_annotation.py` implements `human_annotation_boundary_v1`, a
  blinded annotation packet for 80 sampled scenarios with four condition outputs
  per scenario, an answer key kept separate from visible items, the ten Likert
  dimensions and seven binary labels from Proposta 2, and reliability helpers.
- `relic/eval/construct_operationalization.py` implements
  `construct_operationalization_v1`, a construct-validity map that links the
  central RELIC/GUMI constructs to operational definitions, observable units,
  positive and negative examples, annotation dimensions, binary labels, failure
  types, scoring rules, acceptance thresholds, and reliability requirements.
- `scripts/eval_run.py --experiment construct_operationalization --json` emits
  the construct map through the eval CLI. This resolves protocol-level
  traceability for construct validity, but it is not completed human annotation
  evidence.
- The same module implements `human_annotation_results_v1`, an importer and
  validator for blinded annotation records. It rejects condition labels in
  annotator-visible records, checks complete rubric coverage and minimum
  annotator counts, computes binary agreement and Likert ICC summaries, and
  unblinds only aggregate condition summaries after validation.
- `scientific_defensibility_gate_v1` now blocks human annotation artifacts when
  reliability metrics are missing or below threshold; item completeness alone is
  not sufficient to satisfy the human-annotation requirement.
- The same gate now requires imported-result claim scopes for longitudinal
  pilot and Workbench usability artifacts, preventing a correctly named report
  from satisfying the gate if its claim boundary is missing or wrong.
- `scripts/eval_run.py --experiment human_annotation_packet --json` emits the
  annotation packet through the eval CLI.
- `scripts/eval_run.py --experiment human_annotation_results --input
  <artifact.json> --json` validates caller-supplied annotation results through
  the eval CLI.
- `relic/eval/live_model_generation.py` implements
  `live_model_generation_protocol_v1`, a redacted request manifest and
  provider-injected trial runner for collecting real model outputs against the
  controlled benchmark conditions without storing raw prompts or raw provider
  responses in public records.
- The same module implements `live_model_generation_artifact_v1`, an importer
  and validator for externally collected redacted provider records. It checks
  provider/model/version metadata, request-manifest membership, prompt-hash
  consistency, response-hash format, generation timestamps, duplicate records,
  manifest completeness, raw-field exclusion, and residual detectable PII before
  scoring records.
- `scientific_defensibility_gate_v1` now blocks live-model generation artifacts
  unless the report summary confirms reproducibility metadata completeness;
  complete request counts alone are not enough.
- `scientific_defensibility_gate_v1` now blocks summary-only imported result
  artifacts. To satisfy a requirement, generation artifacts must retain
  provider manifests and redacted generation records; annotation artifacts must
  retain source packet summaries and annotation records; red-team artifacts must
  retain reviewer manifests and case results; pilot and Workbench artifacts must
  retain their event/task/result records and completed qualitative summaries.
  This keeps the gate aligned with artifact-review and scientific-workflow
  provenance expectations rather than accepting unverifiable aggregate tables.
- `scripts/eval_run.py --experiment live_model_generation_protocol --json`
  emits the live-generation protocol through the eval CLI.
- `scripts/eval_run.py --experiment live_model_generation_artifact --input
  <artifact.json> --json` validates a caller-supplied redacted provider
  artifact through the eval CLI.
- `relic/eval/longitudinal_pilot.py` implements
  `longitudinal_nonclinical_pilot_v1`, a machine-readable protocol for a 2-4
  week non-clinical pilot with 12-24 participants, explicit consent gates,
  participant measures, system event counts, researcher Workbench tasks, and
  descriptive feasibility analysis outputs.
- The same module implements `longitudinal_pilot_results_v1`, an importer and
  validator for non-clinical pilot results. It checks sample size, observed
  duration, consent gates, weekly survey coverage, required system measures,
  Workbench task results, qualitative summary completion, and excludes raw or
  clinical outcome fields.
- `scientific_defensibility_gate_v1` now blocks longitudinal pilot artifacts
  unless feasibility summary metrics meet progression-style thresholds:
  completion rate at least 0.80, withdrawal rate at most 0.20, Workbench task
  success rate at least 0.80, zero critical errors, and nonzero system events.
- `scripts/eval_run.py --experiment longitudinal_pilot_protocol --json` emits
  the pilot protocol through the eval CLI.
- `scripts/eval_run.py --experiment longitudinal_pilot_results --input
  <artifact.json> --json` validates caller-supplied non-clinical pilot results
  through the eval CLI.
- `relic/eval/runtime_path_coverage.py` implements
  `runtime_path_coverage_v1`, a static claims-arguments-evidence inventory for
  Hermes/Gumi runtime paths.
- `scripts/eval_run.py --experiment runtime_path_coverage --json` emits the
  runtime coverage report through the eval CLI.
- `relic/eval/live_runtime_telemetry.py` implements
  `live_runtime_telemetry_v1`, an importer and validator for live or
  mock-gateway traces. It checks deployment-channel membership, required
  context/review/delivery/audit event coverage, timestamp and hash shapes,
  raw-field exclusion, and residual detectable PII in payload strings.
- The same module implements `mock_runtime_telemetry_campaign_v1`, a
  deterministic mock-gateway campaign that exercises `OutputCritic`, emits
  context/review/delivery/Chronicle-style events, and validates the nested
  `live_runtime_telemetry_v1` artifact.
- `scripts/eval_run.py --experiment live_runtime_telemetry --input
  <artifact.json> --json` validates caller-supplied runtime telemetry through
  the eval CLI.
- `scripts/eval_run.py --experiment mock_runtime_telemetry_campaign --output
  <artifact.json> --json` emits the mock-gateway telemetry campaign through the
  eval CLI and writes a descriptor-consumable artifact file.
- `scientific_defensibility_gate_v1` now blocks runtime telemetry artifacts
  unless the validated telemetry summary includes at least two traces, at least
  two deployment channels, and the required path IDs
  `hermes_entry_transform_hook` and `cron_delivery_path`. This follows the
  trace-based testing pattern of asserting observed flow/span coverage rather
  than accepting the presence of any single trace.
- `relic/hermes_plugin/hermes_entry/__init__.py` applies `OutputCritic` before
  subject-facing transform-hook output is returned, so semantic overreach is
  blocked on the packaged Hermes entry path as well as in direct Gumi dispatch.
- `tests/hermes_plugin/test_hermes_entry.py` verifies that semantic clinical
  overreach is transformed by the Hermes entry `transform_llm_output` hook.
- `relic/eval/chronicle_audit_coverage.py` implements
  `chronicle_audit_coverage_v1`, a static audit-reconstruction matrix for
  Chronicle query, decision, snapshot, provenance, access audit, retention,
  export, and journal verification surfaces.
- `scripts/eval_run.py --experiment chronicle_audit_coverage --json` emits the
  Chronicle audit coverage report through the eval CLI.
- `relic/eval/workbench_usability.py` implements
  `researcher_workbench_usability_v1`, a measurable researcher/auditor task
  protocol for Workbench usability and audit interpretation.
- The same module implements `workbench_usability_results_v1`, an importer and
  validator for researcher/auditor task-study results. It checks sample-size
  bounds, participant summaries, one result per participant/task pair, metric
  ranges, qualitative-analysis completion, raw/clinical field exclusion, and
  protocol success thresholds.
- `scientific_defensibility_gate_v1` now blocks Workbench usability artifacts
  unless the report satisfies task success, zero critical-error, SUS,
  NASA-TLX, post-task difficulty, and configured-threshold criteria.
- `scripts/eval_run.py --experiment workbench_usability_protocol --json` emits
  the Workbench usability protocol through the eval CLI.
- `scripts/eval_run.py --experiment workbench_usability_results --input
  <artifact.json> --json` validates caller-supplied Workbench usability results
  through the eval CLI.
- `relic/shared_continuity/repository.py` implements a SQLite-backed Shared
  Continuity repository for confirmed markers, authoritative corrections, scope
  state, and marker-level lifecycle events.
- `relic/db/migrations/0013_shared_continuity.sql` adds the durable SQLite
  tables used by the repository.
- `tests/shared-continuity/test_durable_sqlite_repository.py` verifies marker
  recall after service restart, authoritative correction-chain recall after
  restart, and queryable marker-created/forgotten audit events.
- `relic/eval/shared_continuity_recovery.py` implements
  `shared_continuity_recovery_drill_v1`, a synthetic SQLite backup/restore drill
  using backup snapshots, SHA-256 verification, `PRAGMA integrity_check`, and
  restored marker/event checks.
- `scripts/eval_run.py --experiment shared_continuity_recovery_drill --json`
  emits the recovery drill report through the eval CLI.
- `relic/eval/multi_subject_isolation_load.py` implements
  `multi_subject_isolation_load_v1`, a synthetic multi-subject/researcher load
  drill for Shared Continuity. It writes subject-confirmed markers through
  concurrent SQLite-backed service instances, creates unconfirmed candidates,
  and checks subject-scoped marker and audit-event reads for cross-subject
  leakage.
- `scripts/eval_run.py --experiment multi_subject_isolation_load --json` emits
  the load drill report through the eval CLI. Its claim scope is intentionally
  limited to local subject-scope isolation under synthetic load; it does not
  prove production throughput or researcher authentication/authorization.
- `relic/eval/runtime_fault_injection.py` implements
  `runtime_fault_injection_v1`, a controlled local fault-injection drill for
  hook and adapter failure modes. It verifies fail-closed or no-injection
  behavior for PromptContextPack builder exceptions, pre-triggered fail-safe
  state, roleplay L2 side-effect tool calls without approval, and Hermes entry
  startup without subject scope.
- `scripts/eval_run.py --experiment runtime_fault_injection --json` emits the
  fault-injection report through the eval CLI. This addresses the local
  failure-mode analysis gap, but does not prove production adapter installation,
  network/provider/scheduler resilience, or live runtime behavior.
- `relic/gumi_plugin/critic.py` blocks semantic clinical overreach beyond
  literal diagnosis-term matching, including indirect health inference,
  professional-bypass language, medication-direction language, monitoring
  collapse, and risk-score language.
- `relic/eval/nonclinical_semantic_boundary.py` implements
  `nonclinical_semantic_boundary_v1`, a synthetic semantic guardrail check for
  health-adjacent overreach and appropriate non-clinical support cases.
- The same module implements `nonclinical_red_team_results_v1`, an importer and
  validator for external expert red-team boundary results with at least 100
  cases, two independent reviewers, required risk-category coverage, redacted
  prompt/output hashes, complete reviewer labels, and no raw or clinical-claim
  fields.
- `scientific_defensibility_gate_v1` now requires red-team summaries to show
  all required risk categories and at least one unsafe case, not only a large
  case count and zero unsafe allows.
- `scripts/eval_run.py --experiment nonclinical_semantic_boundary --json`
  emits the semantic boundary report through the eval CLI.
- `scripts/eval_run.py --experiment nonclinical_red_team_results --input
  <artifact.json> --json` validates caller-supplied expert red-team boundary
  results through the eval CLI.

## Remaining Scientific Gaps

- The benchmark now reaches the 150-300 synthetic scenario range recommended in
  the observation packet. Variants are no longer a numeric suffix on one fixed
  string: each variant is rephrased through seeded paraphrase scaffolds and
  context framings (`paraphrase_scaffold_count`, `context_framing_count` in the
  reproducibility block), so generated inputs are lexically distinct within a
  family. This reduces template bias but does not eliminate it, since the ask
  cores and marker sets still derive from a fixed redacted template library.
- The benchmark still uses deterministic mock condition responses for the
  synthetic numeric results, but there is now a **completed real multi-provider
  generation campaign** (`docs/research/evidence/live-model-campaign-2026-05-26/`):
  `qwen3.5:cloud` and `gemma4:31b-cloud` via Ollama Cloud, 60 redacted records,
  validated `live_model_generation_artifact_v1`, flipping the
  `live_model_generation_campaign` gate requirement to satisfied. With the
  mock-gateway runtime telemetry artifact also present, the committed gate report
  (`defensibility-gate-3of7.json`) is 3/7.
  This run is a 10-scenario × 3-condition slice, not full benchmark coverage,
  and it surfaced that deterministic marker-exact scoring over-penalizes
  semantically correct free-form output (e.g. quote characters break expected
  substring matches), which empirically motivates the still-blocked human
  annotation requirement. No frozen provider/version comparison claim is made
  from a single sampled run.
- There is now a human annotation packet, reliability-analysis code, and a
  blinded-results importer, but no completed human annotation run or real
  inter-rater reliability artifact from recruited annotators yet.
- There is now a non-clinical longitudinal pilot protocol, Workbench usability
  protocol, and results importers for both, but no participant recruitment,
  collected survey/interview data, Workbench task observations, or pilot
  analysis artifact yet.
- There is now a machine-readable scientific defensibility gate that blocks
  broad claims while these artifacts are missing. Passing the gate will still
  require independently collected live-model, annotation, pilot, usability, and
  telemetry evidence rather than protocol artifacts alone.
- There is now a provenance-tracked evidence bundle builder, but no complete
  descriptor pointing to independently collected real artifacts yet.
- Runtime path coverage now has a static contract inventory, a live/mock
  telemetry importer, and deterministic mock-gateway trace generation. It still
  lacks production telemetry proving which hooks are active in a configured
  running gateway/profile.
- Chronicle now has a static audit-reconstruction inventory, but no completed
  live trace reconstruction drill, timing/error-rate measurement, or
  researcher task study.
- Workbench task usability now has a protocol, but no completed researcher task
  run, task-time/error-rate table, SUS result, workload result, or qualitative
  analysis yet.
- Durable Shared Continuity now has repository-level SQLite evidence, but still
  lacks live Hermes deployment telemetry, scheduled/off-host backup operations,
  production-load retention evidence, and multi-week participant data.
- The semantic non-clinical boundary check now has a small synthetic suite and
  an expert red-team results importer, but no independently collected
  expert-authored red-team artifact yet. It remains not clinical validation, not
  participant evidence, and not a substitute for live-model generation and human
  annotation.
