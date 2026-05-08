# Example Replication Bundle

This directory contains a minimal example replication bundle demonstrating the structure defined by the replication schemas.

## Contents

```
example_bundle/
├── run_manifest.json           # Execution metadata and reproducibility class
├── artifact_checksums.json     # SHA-256 checksums of compiled artifacts
├── environment.txt             # Pinned dependency versions
├── fixtures/                   # Deterministic input fixtures
│   └── example_input.json
└── expected_outputs/           # Expected output fixtures
    └── eval_results.json
```

## Usage

Use this as a template for creating replication bundles:

1. Copy the structure to your bundle directory
2. Populate with your actual run data
3. Run `make replication-bundle` to validate the bundle
4. Verify checksums with `artifact_checksums.json`

## Privacy Notes

This example bundle contains only synthetic/redacted data. No real private user data is included.
