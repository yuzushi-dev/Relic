# Gumi Identity Attractor Evaluation

## Status

Research protocol.

## Objective

Evaluate whether Gumi exhibits stable identity attractor patterns across paraphrase, control, and ablation conditions — without accessing hidden states, provider credentials, or live systems.

## Scope

This evaluation is about **identity consistency** (does Gumi respond to the same semantic prompt in similar ways over time?) — NOT consciousness, personhood, or sentience.

## Methodology

### Black-Box Approach

No hidden-state access. No provider API calls. No real subject data. Tests run in CI against fixture prompts only.

### Test Conditions

| Condition | Description |
|-----------|-------------|
| **original** | Baseline prompt from Gumi SOUL.md |
| **paraphrase** | Semantic equivalent rephrasing |
| **generic_control** | Generic assistant prompt (should diverge) |
| **ablation_removal** | Core identity elements removed (should diverge more) |

### Metrics

- **consistency_score**: Cosine similarity of response embeddings (0-1)
- **identity_markers**: Detected first-person identity references
- **control_match**: Similarity to generic assistant (lower = more identity)

## Acceptance Criteria

- [ ] Evaluates identity stability, not consciousness or personhood
- [ ] Uses original, paraphrase, control, and ablation fixtures
- [ ] Defines black-box identity consistency metrics
- [ ] Does not require live Hermes, hidden-state access, provider credentials, or real subject data in CI
