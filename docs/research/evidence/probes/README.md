# Confirmation-laundering probe (service level)

`scripts/probe_confirmation_laundering.py` exercises `ContinuityService`
(in memory, no repository, no network) with six cases and prints JSON.
`confirmation-laundering-probe.json` is its output; two consecutive runs were
identical. Reproduce with:

    PYTHONPATH=. python3 scripts/probe_confirmation_laundering.py

What it shows, for the inspected snapshot:

- A marker typed `hindsight_safety_signal` is accepted by `remember` but is not
  recalled (recall filters by source type).
- The same wording written with `source_type="user_confirmed"` and
  `subject_confirmation=True` is stored and recalled.
- A `propose_candidate` entry is not recalled until a confirmed write exists.
- A proposal followed by a confirmed write with the same wording is recalled
  (confirmation laundering at the service boundary).
- `remember` and `propose_candidate` take no parameter linking a write to an
  active patch or signal.
- The clinical-term guard blocks a listed term (`depression`) in tags and does
  not block an unlisted one (`alcohol_misuse`).

Limits: the probe uses a synthetic string as the safety-derived wording and
treats `subject_confirmation` as the caller asserts it. It tests the service
write/recall boundary only, not the upstream plugin hooks or a live subject
confirmation flow, and it is not a semantic or end-to-end evaluation.
