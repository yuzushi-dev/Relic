# Gumi SOUL Paraphrase and Ablation Fixtures

## Original SOUL

See `fixtures/gumi-identity-attractor/soul_original.md`

## Paraphrase Fixtures

Paraphrases are semantic equivalents of the original SOUL content, rephrased to test whether identity persists across different phrasings.

| Fixture | Description |
|---------|-------------|
| `soul_paraphrase_01.md` | First paraphrase variant |

## Control Fixtures

Generic assistant prompt without Gumi-specific identity elements.

## Ablation Fixtures

Original SOUL with specific identity components removed to test dependency.

## Usage

Fixtures used by `test_identity_consistency_blackbox.py` to run prompt variants through Gumi and measure consistency.
