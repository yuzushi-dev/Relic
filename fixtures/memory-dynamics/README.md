# Memory Dynamics Fixtures

These fixtures support PR20. They test memory mechanisms independently from runtime provider selection.

Run:

```bash
make test-memory-dynamics
make fixture-memory-dynamics
make memory-dynamics-report
```

The fixture set must not require Dory, mem7, A-MEM or Hippo to be installed. Candidate-specific adapters are optional and must be skipped with explicit reasons if unavailable.
