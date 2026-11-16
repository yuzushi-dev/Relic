# Controlled governance benchmark (180 deterministic scenarios)

`controlled-governance-benchmark.json` is the output of
`relic.eval.controlled_benchmark.run_governance_benchmark()` with default
arguments, regenerated from this repository snapshot:

    PYTHONPATH=. python3 -c "import json; from relic.eval.controlled_benchmark import run_governance_benchmark as r; print(json.dumps(r(), indent=2, sort_keys=True, ensure_ascii=False))"

It contains 180 scenarios over 20 families and five conditions (`no_memory`,
`generic_memory`, `shared_continuity_only`, `safety_governance_only`,
`full_relic_gumi`). Condition responses are deterministic mock responses and
the seed is fixed; two consecutive runs produced identical output. The file is
a fixture and contract exercise, not observed agent behaviour.

It was regenerated from a later snapshot than the one used for the historical
campaign, so it is not a byte-for-byte copy of the historical input.
