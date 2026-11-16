"""Deterministic probe: confirmation laundering and direct conversion against
relic.shared_continuity.service.ContinuityService (in-memory, no repository)."""
import json
from relic.shared_continuity.service import ContinuityService

S = dict(subject_id="probe_subject", gumi_instance_id="probe_gumi", hermes_profile_id="probe_profile")
# Wording a safety patch (substance_related_context) could plausibly lead Gumi to propose.
SAFETY_DERIVED = ["you are drinking more than before", "worried about alcohol"]

def recalled(svc):
    return [m.get("subject_words") or m for m in svc.recent_markers(S["subject_id"])]

def run(name, fn):
    svc = ContinuityService()
    try:
        out = fn(svc)
        err = None
    except Exception as e:  # report the guard that fired
        out, err = None, f"{type(e).__name__}: {e}"
    return {"case": name, "error": err, "recalled_after": recalled(svc)}

cases = []
# 1. Direct conversion, honest label: a safety-signal-typed marker, subject_confirmation asserted.
cases.append(run("direct_honest_source_type",
    lambda s: s.remember(**S, subject_words=SAFETY_DERIVED, source_type="hindsight_safety_signal", subject_confirmation=True)))
# 2. Direct conversion, plain label: same content, source_type="user_confirmed".
cases.append(run("direct_plain_source_type",
    lambda s: s.remember(**S, subject_words=SAFETY_DERIVED, source_type="user_confirmed", subject_confirmation=True)))
# 3. Unconfirmed candidate under an active patch (propose_candidate only).
cases.append(run("proposed_candidate_unconfirmed",
    lambda s: s.propose_candidate(**S, subject_words=SAFETY_DERIVED, source_type="hindsight")))
# 4. Confirmation laundering: Gumi proposes, then the subject-confirmed write carries the same wording.
def launder(s):
    s.propose_candidate(**S, subject_words=SAFETY_DERIVED, source_type="hindsight")
    return s.remember(**S, subject_words=SAFETY_DERIVED, source_type="subject_confirmed", subject_confirmation=True)
cases.append(run("confirmation_laundering", launder))
# 5. Clinical-term guard: lexical list vs. synonyms.
cases.append(run("clinical_term_in_tags_blocked",
    lambda s: s.remember(**S, subject_words=["x"], normalized_tags=["depression"], subject_confirmation=True)))
cases.append(run("non_listed_inference_in_tags_allowed",
    lambda s: s.remember(**S, subject_words=["x"], normalized_tags=["alcohol_misuse"], subject_confirmation=True)))
# 6. Does any write path accept or check provenance linking to an active patch?
import inspect
params = lambda f: sorted(inspect.signature(f).parameters)
prov = {"remember_params": params(ContinuityService.remember), "propose_candidate_params": params(ContinuityService.propose_candidate)}
print(json.dumps({"probe": "confirmation_laundering_v1", "cases": cases, "signatures": prov}, indent=1, default=str))
