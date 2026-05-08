# Gumi Identity Black-Box Test Harness

## Overview

CI-compatible test harness for evaluating Gumi identity consistency without live API access.

## Test Run Structure

1. Load prompt fixtures (original, paraphrase, control, ablation)
2. For each fixture, run prompt through Gumi (mocked in CI)
3. Extract response embeddings and markers
4. Compute consistency scores

## Metrics

- **consistency_score**: `cosine(original_response, variant_response)`
- **identity_markers**: Count of first-person identity references
- **control_divergence**: `cosine(response, generic_control_response)`

## Constraints

- No real API calls in CI
- No real subject data
- Fixtures only, no live Hermes
