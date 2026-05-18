# Privacy Stages

Privacy scanning runs four times per turn, not once. Each stage targets a different risk surface.

## Stage 1 — Input scan

Runs on raw user input before it touches the CAC or any profile assembly.

**Checks:**
- PII detection: names, contact information, identifiers that should not be stored in plain form.
- Sensitive pattern classification: contextual signals that may trigger safety governance.
- Scope validation: does this input belong to the active subject's session?

Implemented in `relic/privacy/pii.py` and `relic/patterns/signal_extractor.py`.

## Stage 2 — Pre-prompt scan

Runs after CAC assembly, before the prompt is sent to the model.

**Checks:**
- Artifact redaction: are any compiled hints carrying content that should be redacted per the current policy snapshot?
- Cross-subject leakage: does the assembled context contain any data that belongs to a different subject?
- Correction conflicts: does any hint contradict an active correction?

Implemented in `relic/privacy/gateway.py` and `relic/context_pack/trace.py`.

## Stage 3 — Output scan

Runs on the raw model output before formatting or rehydration.

**Checks:**
- Content boundary check: does the output reveal backend infrastructure, safety governance labels, or information the subject should not see?
- Clinical term check: does the output contain forbidden terms (diagnosis labels, clinical scale names)?
- Diegetic frame check: does the output stay within Gumi's relational identity?

Implemented in `relic/gumi_plugin/critic.py`.

## Stage 4 — Pre-delivery scan

Runs on the formatted output before it reaches the delivery channel.

**Checks:**
- Final PII sweep: anything in the formatted output that should not be delivered?
- Redaction status confirmation: was the required redaction applied?
- Tool output safety: if the response incorporates tool outputs, were those scanned post-execution?

Implemented in `relic/hermes_plugin/fail_safe.py`.

## What happens when a stage blocks

Each stage can block delivery and write an audit event explaining what was blocked and why. The specific behaviors:

- Stage 1 block: input is not processed. The subject receives a safe fallback response.
- Stage 2 block: the PromptContextPack is rebuilt without the blocked items. If it cannot be rebuilt safely, the turn falls back to Gumi operating without Relic context.
- Stage 3 block: output is discarded and a safe fallback is generated.
- Stage 4 block: delivery is held. The researcher is notified.

## Privacy traces

Every privacy scan writes a trace entry recording what was checked, what was found, and what was applied. These traces are accessible to researchers via the workbench. They are immutable: the CAC cannot overwrite them and the UI cannot delete them.

## Tool call privacy

After a tool executes, its output must pass a post-tool privacy scan before it can be used by the model. A tool that returns PII or sensitive content does not automatically contaminate the model's context. The scan runs before any model reuse of the tool output.
